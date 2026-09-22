"""
TERRA-CORE-DRILL — point d'entrée du pipeline géophysique.

Le script orchestre quatre étages bornés :

1. optimisation du blindage en dix couches ;
2. génération d'un profil géologique paramétrique par générateur ;
3. décodage/agrégation de capteurs et décision Thermal Lock ;
4. écriture atomique d'un checkpoint JSON toutes les dix secondes de temps
   mur, plus un manifeste Markdown à la fin du run.

Le profil n'est pas une simulation de longue durée et ne lance aucun rendu 3-D.
Il est volontairement court et déterministe pour tester l'architecture et les
contrats de données. Les nombres géophysiques doivent être remplacés par des
profils calibrés avant tout usage scientifique ou matériel.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import struct
import tempfile
import time
from typing import Deque, Dict, Iterator, Optional, Tuple

from drill_control_hpc import DriftSolution, ThermalLockController, solve_drift_vectors
from geological_sensors import (
    MAGNETOMETER,
    PIEZOELECTRIC_PRESSURE,
    SensorRegistry,
    encode_frame,
)
from shield_optimizer import (
    DEFAULT_BLOCK_SHAPE,
    DEFAULT_GRID_SHAPE,
    HoneycombSpec,
    ShieldOptimizationResult,
    optimize_shield,
)


# ---------------------------------------------------------------------------
# Domaine paramétrique du pipeline
# ---------------------------------------------------------------------------

MOHO_DEPTH_M = 35_000.0
CORE_MANTLE_BOUNDARY_DEPTH_M = 2_890_000.0
INNER_CORE_BOUNDARY_DEPTH_M = 5_150_000.0
EARTH_CENTER_DEPTH_M = 6_371_000.0
THERMAL_LOCK_SENSOR_OFFSET_M = 1.75
DEFAULT_CHECKPOINT_INTERVAL_S = 10.0
DEFAULT_SAMPLE_COUNT = 48


@dataclass(frozen=True)
class TraversalConfig:
    """Configuration bornée d'un run de validation logicielle."""

    start_depth_m: float = MOHO_DEPTH_M
    end_depth_m: float = EARTH_CENTER_DEPTH_M
    samples: int = DEFAULT_SAMPLE_COUNT
    checkpoint_interval_s: float = DEFAULT_CHECKPOINT_INTERVAL_S
    checkpoint_path: Path = Path("TERRA_DRILL_CHECKPOINT.json")
    manifest_path: Path = Path("TERRA_DRILL_MANIFEST.md")
    thermal_lock_sensor_offset_m: float = THERMAL_LOCK_SENSOR_OFFSET_M

    def __post_init__(self) -> None:
        if self.start_depth_m < 0.0 or self.end_depth_m <= self.start_depth_m:
            raise ValueError("intervalle de profondeur invalide")
        if self.samples < 2:
            raise ValueError("samples doit être >= 2")
        if self.checkpoint_interval_s <= 0.0:
            raise ValueError("checkpoint_interval_s doit être positif")
        if self.thermal_lock_sensor_offset_m <= 0.0:
            raise ValueError("thermal_lock_sensor_offset_m doit être positif")


@dataclass
class DrillState:
    """État sérialisable de la foreuse au point courant du profil."""

    run_id: str
    sample_index: int
    sample_count: int
    simulation_time_s: float
    depth_m: float
    phase: str
    temperature_c: float
    pressure_pa: float
    density_kg_m3: float
    thermal_lock_sensor_offset_m: float
    thermal_lock: bool
    angular_speed_rad_s: float
    coolant_flow_kg_s: float
    axial_feed_m_s: float
    drift_vector_m_s: Tuple[float, float, float]
    shield_active: bool
    checkpoint_reason: str = "periodic"
    updated_utc: str = ""

    def to_dict(self) -> Dict[str, object]:
        value = asdict(self)
        value["drift_vector_m_s"] = list(self.drift_vector_m_s)
        return value


class CheckpointManager:
    """Écrit un JSON atomiquement sans thread de fond.

    ``maybe_write`` est appelé depuis la boucle principale. Une écriture est
    déclenchée après ``interval_s`` de temps mur ou de temps simulé, et les
    appels ``force=True`` garantissent un état initial et final même si le run
    est très court.
    """

    def __init__(self, path: Path, interval_s: float = DEFAULT_CHECKPOINT_INTERVAL_S):
        if interval_s <= 0.0:
            raise ValueError("interval_s doit être positif")
        self.path = Path(path)
        self.interval_s = float(interval_s)
        self._last_write_monotonic: Optional[float] = None
        self._last_write_simulation_s: Optional[float] = None
        self.write_count = 0

    def maybe_write(
        self,
        state: DrillState,
        force: bool = False,
        simulation_time_s: Optional[float] = None,
    ) -> bool:
        now = time.monotonic()
        wall_due = (
            self._last_write_monotonic is None
            or now - self._last_write_monotonic >= self.interval_s
        )
        simulated_due = (
            simulation_time_s is not None
            and (
                self._last_write_simulation_s is None
                or simulation_time_s - self._last_write_simulation_s >= self.interval_s
            )
        )
        due = force or wall_due or simulated_due
        if not due:
            return False
        state.updated_utc = datetime.now(timezone.utc).isoformat()
        state.checkpoint_reason = "forced" if force else "periodic"
        self._atomic_write(state.to_dict())
        self._last_write_monotonic = now
        if simulation_time_s is not None:
            self._last_write_simulation_s = float(simulation_time_s)
        self.write_count += 1
        return True

    def _atomic_write(self, payload: Dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # NamedTemporaryFile dans le même dossier garantit que os.replace est
        # atomique sur le volume local, sans laisser un JSON partiellement écrit.
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(self.path.parent),
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            delete=False,
        )
        temporary_name = Path(handle.name)
        try:
            with handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
        finally:
            if temporary_name.exists():
                temporary_name.unlink()


# ---------------------------------------------------------------------------
# Profil géophysique et trames de validation
# ---------------------------------------------------------------------------


def _phase_for_depth(depth_m: float) -> str:
    if depth_m < CORE_MANTLE_BOUNDARY_DEPTH_M:
        return "manteau_silicate"
    if depth_m < INNER_CORE_BOUNDARY_DEPTH_M:
        return "noyau_externe_liquide_fer_nickel"
    return "noyau_interne_fer_nickel"


def _geophysical_profile(depth_m: float) -> Tuple[float, float, float]:
    """Retourne T, P et densité d'un profil de test monotone.

    Ces relations linéaires par morceaux stabilisent le banc logiciel ; elles
    ne remplacent pas une table PREM, une inversion sismologique ou une base
    thermodynamique. La pression maximale est volontairement paramétrée à
    360 GPa afin d'exercer les limites numériques demandées.
    """

    normalized = (depth_m - MOHO_DEPTH_M) / (EARTH_CENTER_DEPTH_M - MOHO_DEPTH_M)
    normalized = max(0.0, min(1.0, normalized))
    temperature_c = 800.0 + 5_200.0 * normalized
    pressure_pa = 1.0e9 + (360.0e9 - 1.0e9) * normalized
    phase = _phase_for_depth(depth_m)
    if phase == "manteau_silicate":
        density = 3_350.0 + 1_000.0 * normalized
    elif phase == "noyau_externe_liquide_fer_nickel":
        density = 9_900.0 + 800.0 * normalized
    else:
        density = 12_200.0 + 400.0 * normalized
    return temperature_c, pressure_pa, density


def iter_depth_samples(config: TraversalConfig) -> Iterator[Tuple[int, float]]:
    """Génère des points de profondeur sans construire une liste globale."""

    step = (config.end_depth_m - config.start_depth_m) / (config.samples - 1)
    for index in range(config.samples):
        yield index, config.start_depth_m + index * step


def _build_validation_frames(
    sequence: int,
    timestamp_ms: int,
    temperature_c: float,
    pressure_pa: float,
    phase: str,
) -> Tuple[bytes, bytes]:
    """Crée deux trames synthétiques pour exercer le registre sans I/O externe."""

    # Magnétomètre : champ et conductivité indicatifs du noyau liquide.
    conductivity = 1.0e6 if "noyau_externe" in phase else 2.0e5
    magnetometer_payload = struct.pack(
        "<fffff",
        2.0e-5,
        1.0e-5,
        3.0e-5,
        temperature_c,
        conductivity,
    )
    magnetometer_frame = encode_frame(
        MAGNETOMETER,
        sequence,
        timestamp_ms,
        magnetometer_payload,
    )

    pressure_payload = struct.pack("<ff", pressure_pa, 2.5)
    pressure_frame = encode_frame(
        PIEZOELECTRIC_PRESSURE,
        sequence,
        timestamp_ms,
        pressure_payload,
    )
    return magnetometer_frame, pressure_frame


# ---------------------------------------------------------------------------
# Rapport et orchestration
# ---------------------------------------------------------------------------


def _fmt(value: float, digits: int = 3) -> str:
    if math.isinf(value):
        return "∞"
    return f"{value:,.{digits}f}"


def _markdown_manifest(
    config: TraversalConfig,
    run_id: str,
    shield: ShieldOptimizationResult,
    recent_states: Deque[DrillState],
    phase_counts: Dict[str, int],
    thermal_lock_events: int,
    sensor_registry: SensorRegistry,
    checkpoint_manager: CheckpointManager,
) -> str:
    """Construit le manifeste à partir de résumés à mémoire constante."""

    lines = [
        "# TERRA-CORE-DRILL — TERRA_DRILL_MANIFEST",
        "",
        "> Rapport généré par `core_main.py`. Il s'agit d'un banc logiciel",
        "> paramétrique et non d'une validation de faisabilité d'un forage réel.",
        "",
        "## Identité du run",
        "",
        f"- Run ID : `{run_id}`",
        f"- Généré UTC : `{datetime.now(timezone.utc).isoformat()}`",
        f"- Profondeur initiale : **{_fmt(config.start_depth_m, 1)} m**",
        f"- Profondeur finale : **{_fmt(config.end_depth_m, 1)} m**",
        f"- Échantillons : **{config.samples}** (générateur, sans liste de profil)",
        f"- Capteur Thermal Lock : **{config.thermal_lock_sensor_offset_m:.2f} m** en amont de la tête",
        "",
        "## Contrat mémoire et exécution",
        "",
        "- Géométrie du blindage : blocs NumPy alternés, aucune matrice globale.",
        "- Agrégation des capteurs : statistiques de Welford et historique borné.",
        "- Checkpoint : écriture JSON atomique depuis la boucle principale, sans tâche de fond.",
        f"- Fichier checkpoint : `{checkpoint_manager.path}` ({checkpoint_manager.write_count} écriture(s))",
        "- Aucun rendu 3-D et aucune simulation physique longue ne sont lancés.",
        "",
        "## Blindage en tungstène — 10 couches",
        "",
        f"- Densité nominale : **{shield.nominal_density_g_cm3:.2f} g/cm³**",
        f"- Densité cible : **{shield.target_density_g_cm3:.2f} g/cm³**",
        f"- Porosité théorique cible : **{100.0 * (1.0 - shield.target_density_ratio):.2f} %**",
        f"- Fraction solide modélisée : **{100.0 * shield.modeled_solid_fraction:.2f} %**",
        f"- Densité issue du raster : **{shield.modeled_density_g_cm3:.3f} g/cm³**",
        f"- Écart à la cible : **{shield.density_error_g_cm3:+.3f} g/cm³**",
        f"- Réduction massique nominale : **{shield.mass_reduction_percent:.2f} %**",
        f"- Maille : {shield.geometry.cell_pitch_nm:g} nm, paroi {shield.geometry.wall_thickness_nm:g} nm, "
        f"{shield.geometry.pixels_per_cell} pixels/maille",
        "",
        "### Transfert thermique de Fourier",
        "",
        f"- Température initiale : **{shield.thermal.initial_temperature_c:.1f} °C**",
        f"- Température de bord : **{shield.thermal.boundary_temperature_c:.1f} °C**",
        f"- Temps estimé vers la cible : **{shield.cooldown_time_s:.2f} s**",
        f"- Température médiane après cooldown : **{shield.temperature_after_cooldown_c:.2f} °C**",
        f"- Flux de surface à cet instant : **{_fmt(shield.peak_surface_heat_flux_w_m2, 2)} W/m²**",
        f"- Diffusivité utilisée : **{shield.thermal_diffusivity_m2_s:.4e} m²/s**",
        "",
        "## Traversée paramétrique",
        "",
        "| Phase | Points |",
        "|---|---:|",
    ]
    for phase, count in sorted(phase_counts.items()):
        lines.append(f"| {phase} | {count} |")

    lines.extend(
        [
            "",
            f"- Points Thermal Lock : **{thermal_lock_events}**",
            f"- Trames capteurs acceptées : **{sensor_registry.frames_ingested}**",
            f"- Trames capteurs rejetées : **{sensor_registry.frames_rejected}**",
            "",
            "### Derniers états échantillonnés",
            "",
            "| Index | Profondeur (m) | Phase | T (°C) | P (GPa) | ω (rad/s) | Débit (kg/s) | Lock |",
            "|---:|---:|---|---:|---:|---:|---:|:---:|",
        ]
    )
    for state in list(recent_states)[-12:]:
        lines.append(
            f"| {state.sample_index} | {_fmt(state.depth_m, 1)} | {state.phase} | "
            f"{_fmt(state.temperature_c, 1)} | {_fmt(state.pressure_pa / 1e9, 2)} | "
            f"{_fmt(state.angular_speed_rad_s, 3)} | {_fmt(state.coolant_flow_kg_s, 3)} | "
            f"{'ACTIF' if state.thermal_lock else 'non'} |"
        )

    lines.extend(
        [
            "",
            "## Données de capteurs",
            "",
            "```json",
            json.dumps(sensor_registry.snapshot(), ensure_ascii=False, indent=2),
            "```",
            "",
            "## Limites et actions de qualification",
            "",
            "1. Remplacer le profil linéaire par une table géophysique versionnée et traçable.",
            "2. Calibrer les coefficients de commande sur un jumeau numérique vérifié puis sur banc instrumenté.",
            "3. Ajouter une validation indépendante des bornes, de la perte de trames et du réarmement Thermal Lock.",
            "4. Ne pas interpréter la géométrie de porosité comme une qualification mécanique du tungstène.",
            "",
            "_Fin du manifeste._",
            "",
        ]
    )
    return "\n".join(lines)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary_name = Path(handle.name)
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name.exists():
            temporary_name.unlink()


def run_pipeline(
    config: TraversalConfig = TraversalConfig(),
    run_id: Optional[str] = None,
    shield: Optional[ShieldOptimizationResult] = None,
) -> Dict[str, object]:
    """Exécute un run borné et génère ``TERRA_DRILL_MANIFEST.md``.

    Le paramètre ``sleep`` n'existe volontairement pas : le pipeline avance à la
    vitesse du banc logiciel. Dans une acquisition réelle, les appels arrivent
    naturellement toutes les dix secondes ou plus souvent et
    ``CheckpointManager`` écrit dès que l'intervalle est dû.
    """

    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    shield = shield or optimize_shield(
        layer_count=10,
        grid_shape=DEFAULT_GRID_SHAPE,
        block_shape=DEFAULT_BLOCK_SHAPE,
        spec=HoneycombSpec(),
        initial_temperature_c=5_500.0,
        target_cooldown_temperature_c=1_000.0,
    )
    checkpoint_manager = CheckpointManager(
        config.checkpoint_path,
        interval_s=config.checkpoint_interval_s,
    )
    registry = SensorRegistry(history_limit=256)
    lock_controller = ThermalLockController()
    recent_states: Deque[DrillState] = deque(maxlen=12)
    phase_counts: Dict[str, int] = {}
    thermal_lock_events = 0
    processed_samples = 0
    last_state: Optional[DrillState] = None

    for index, depth_m in iter_depth_samples(config):
        temperature_c, pressure_pa, density_kg_m3 = _geophysical_profile(depth_m)
        phase = _phase_for_depth(depth_m)
        command: DriftSolution = solve_drift_vectors(
            temperature_c,
            pressure_pa,
            density_kg_m3,
            lock_controller=lock_controller,
        )
        timestamp_ms = index * 1_000
        magnetometer_frame, pressure_frame = _build_validation_frames(
            index,
            timestamp_ms,
            temperature_c,
            pressure_pa,
            phase,
        )
        registry.ingest(magnetometer_frame)
        registry.ingest(pressure_frame)

        state = DrillState(
            run_id=run_id,
            sample_index=index,
            sample_count=config.samples,
            simulation_time_s=float(index),
            depth_m=depth_m,
            phase=phase,
            temperature_c=temperature_c,
            pressure_pa=pressure_pa,
            density_kg_m3=density_kg_m3,
            thermal_lock_sensor_offset_m=config.thermal_lock_sensor_offset_m,
            thermal_lock=command.thermal_lock,
            angular_speed_rad_s=command.angular_speed_rad_s,
            coolant_flow_kg_s=command.coolant_flow_kg_s,
            axial_feed_m_s=command.axial_feed_m_s,
            drift_vector_m_s=command.drift_vector_m_s,
            shield_active=command.thermal_shield_active,
        )
        recent_states.append(state)
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
        thermal_lock_events += int(state.thermal_lock)
        processed_samples += 1
        last_state = state
        checkpoint_manager.maybe_write(
            state,
            force=index == 0,
            simulation_time_s=state.simulation_time_s,
        )

    if last_state is None:
        raise RuntimeError("le pipeline n'a produit aucun état")
    checkpoint_manager.maybe_write(
        last_state,
        force=True,
        simulation_time_s=last_state.simulation_time_s,
    )

    manifest = _markdown_manifest(
        config,
        run_id,
        shield,
        recent_states,
        phase_counts,
        thermal_lock_events,
        registry,
        checkpoint_manager,
    )
    _atomic_write_text(config.manifest_path, manifest)
    return {
        "run_id": run_id,
        "manifest_path": str(config.manifest_path),
        "checkpoint_path": str(config.checkpoint_path),
        "states": processed_samples,
        "thermal_lock_events": thermal_lock_events,
        "sensor_registry": registry.snapshot(),
        "shield": shield.to_dict(),
    }


if __name__ == "__main__":
    # Exécution courte et foreground uniquement. Aucun serveur, thread ou
    # calcul de rendu n'est lancé implicitement.
    summary = run_pipeline()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
