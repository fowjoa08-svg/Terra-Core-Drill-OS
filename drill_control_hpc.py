"""
TERRA-CORE-DRILL — loi de commande autonome de la tête de forage.

Ce module isole la logique de commande d'une boucle d'acquisition. Les
fonctions sont déterministes, sans thread et sans temporisation cachée : le
superviseur appelle ``solve_drift_vectors`` à chaque paquet de télémétrie et
publie la consigne résultante.

Important : les coefficients ci-dessous sont des paramètres de contrôle
logiciel et non des preuves de faisabilité d'une tête de forage réelle. Une
implantation matérielle devrait remplacer les saturations et seuils par des
valeurs issues d'essais, de certification et d'une analyse de sûreté.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Dict, Tuple


# ---------------------------------------------------------------------------
# Constantes de contrôle et unités
# ---------------------------------------------------------------------------

AMBIENT_TEMPERATURE_C = 20.0
REFERENCE_DENSITY_KG_M3 = 3_850.0
REFERENCE_PRESSURE_PA = 1.0e9
REFERENCE_TEMP_MARGIN_C = 2_000.0

# Le seuil est réécrit par la pression : plus la pression augmente, plus la
# marge thermique de commande est réduite. C'est une politique conservatrice,
# pas une température de fusion calculée.
BASE_CRITICAL_TEMPERATURE_C = 2_200.0
PRESSURE_THRESHOLD_COEFF_C_PER_GPA = 0.75
MIN_CRITICAL_TEMPERATURE_C = 900.0
THERMAL_LOCK_HYSTERESIS_C = 100.0

NOMINAL_ANGULAR_SPEED_RAD_S = 8.0
MIN_ANGULAR_SPEED_RAD_S = 0.0
MAX_ANGULAR_SPEED_RAD_S = 18.0
NOMINAL_COOLANT_FLOW_KG_S = 2.0
MAX_COOLANT_FLOW_KG_S = 40.0
NOMINAL_AXIAL_FEED_M_S = 0.02
MAX_AXIAL_FEED_M_S = 0.15


@dataclass(frozen=True)
class ThermalLockConfig:
    """Paramètres de l'interlock thermique avec hystérésis."""

    base_critical_temperature_c: float = BASE_CRITICAL_TEMPERATURE_C
    pressure_coefficient_c_per_gpa: float = PRESSURE_THRESHOLD_COEFF_C_PER_GPA
    minimum_critical_temperature_c: float = MIN_CRITICAL_TEMPERATURE_C
    hysteresis_c: float = THERMAL_LOCK_HYSTERESIS_C

    def critical_temperature_c(self, pressure_pa: float) -> float:
        pressure_gpa = max(0.0, pressure_pa) / 1.0e9
        raw = self.base_critical_temperature_c - (
            self.pressure_coefficient_c_per_gpa * pressure_gpa
        )
        return max(self.minimum_critical_temperature_c, raw)


@dataclass(frozen=True)
class DriftSolution:
    """Consigne complète produite par la loi de commande."""

    temperature_c: float
    pressure_pa: float
    density_kg_m3: float
    pressure_gpa: float
    critical_temperature_c: float
    angular_speed_rad_s: float
    coolant_flow_kg_s: float
    axial_feed_m_s: float
    drift_vector_m_s: Tuple[float, float, float]
    thermal_lock: bool
    cooldown_required: bool
    thermal_shield_active: bool
    lock_reason: str

    def to_dict(self) -> Dict[str, object]:
        result = asdict(self)
        result["drift_vector_m_s"] = list(self.drift_vector_m_s)
        return result

    def __getitem__(self, key: str) -> object:
        """Permet un accès ``solution['thermal_lock']`` pratique en intégration."""

        return self.to_dict()[key]


class ThermalLockController:
    """Machine d'état minimaliste pour le protocole « Thermal Lock ».

    L'interlock s'enclenche au-dessus du seuil critique recalculé à chaque
    mesure. Il ne se réarme qu'après retour sous ``seuil - hystérésis`` et après
    appel explicite à ``request_reset``. Cela évite un oscillateur de commande
    à la frontière thermique.
    """

    def __init__(self, config: ThermalLockConfig = ThermalLockConfig()) -> None:
        self.config = config
        self.latched = False
        self.last_reason = "initialisation"

    def evaluate(self, temperature_c: float, pressure_pa: float) -> bool:
        critical = self.config.critical_temperature_c(pressure_pa)
        if temperature_c > critical:
            self.latched = True
            self.last_reason = (
                f"T={temperature_c:.1f} C > seuil pression-ajusté "
                f"{critical:.1f} C"
            )
        return self.latched

    def request_reset(self, temperature_c: float, pressure_pa: float) -> bool:
        critical = self.config.critical_temperature_c(pressure_pa)
        if temperature_c <= critical - self.config.hysteresis_c:
            self.latched = False
            self.last_reason = "réarmement autorisé après cooldown"
            return True
        self.last_reason = "réarmement refusé : marge d'hystérésis insuffisante"
        return False


def _validate_inputs(temp: float, pressure: float, density: float) -> None:
    if not all(math.isfinite(float(value)) for value in (temp, pressure, density)):
        raise ValueError("temp, pressure et density doivent être finis")
    if pressure < 0.0:
        raise ValueError("pressure doit être exprimée en Pa et non négative")
    if density <= 0.0:
        raise ValueError("density doit être strictement positive en kg/m3")


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def solve_drift_vectors(
    temp: float,
    pressure: float,
    density: float,
    lock_controller: ThermalLockController | None = None,
) -> DriftSolution:
    """Calcule une consigne de dérive, rotation et débit cryogénique.

    Parameters
    ----------
    temp:
        Température locale de la tête en degrés Celsius.
    pressure:
        Pression locale en pascals. 360 GPa s'écrit ``360e9``.
    density:
        Densité apparente de la formation en kg/m³.
    lock_controller:
        Contrôleur optionnel conservant le verrou entre deux appels. Si absent,
        un contrôleur neuf est utilisé pour un appel pur et indépendant.

    Returns
    -------
    DriftSolution
        Consigne bornée. Quand le ``Thermal Lock`` est actif, la vitesse de
        rotation et l'avance axiale sont nulles, le bouclier est déclaré actif
        et le débit de refroidissement est poussé vers sa limite sûre.

    Loi de commande
    ---------------
    Le seuil thermique est ``max(T_min, T_base - k * P_GPa)``. Hors verrou,
    vitesse et avance sont réduites par des facteurs de pression, densité et
    marge thermique. Le vecteur de dérive est un proxy de compensation : sans
    gradients tri-axiaux fournis par les capteurs, il ne prétend pas reconstruire
    un champ mécanique complet.
    """

    _validate_inputs(temp, pressure, density)
    controller = lock_controller or ThermalLockController()
    critical = controller.config.critical_temperature_c(pressure)
    thermal_lock = controller.evaluate(temp, pressure)
    pressure_gpa = pressure / 1.0e9

    # Facteurs bornés : la commande reste stable même si un capteur délivre une
    # valeur très éloignée du domaine nominal.
    pressure_factor = 1.0 / (1.0 + pressure_gpa / 120.0)
    density_factor = math.sqrt(
        _clip(REFERENCE_DENSITY_KG_M3 / max(density, 1.0), 0.05, 4.0)
    )
    margin_denominator = max(critical - AMBIENT_TEMPERATURE_C, 1.0)
    thermal_margin_factor = _clip(
        (critical - temp) / margin_denominator,
        0.0,
        1.0,
    )

    if thermal_lock:
        # Le débit maximal est une action de sûreté ; il ne constitue pas une
        # promesse de refroidissement instantané du matériel réel.
        coolant_flow = MAX_COOLANT_FLOW_KG_S
        angular_speed = MIN_ANGULAR_SPEED_RAD_S
        axial_feed = 0.0
        drift = (0.0, 0.0, 0.0)
        reason = controller.last_reason
        return DriftSolution(
            temperature_c=float(temp),
            pressure_pa=float(pressure),
            density_kg_m3=float(density),
            pressure_gpa=float(pressure_gpa),
            critical_temperature_c=float(critical),
            angular_speed_rad_s=angular_speed,
            coolant_flow_kg_s=coolant_flow,
            axial_feed_m_s=axial_feed,
            drift_vector_m_s=drift,
            thermal_lock=True,
            cooldown_required=True,
            thermal_shield_active=True,
            lock_reason=reason,
        )

    angular_speed = _clip(
        NOMINAL_ANGULAR_SPEED_RAD_S
        * pressure_factor
        * density_factor
        * (0.25 + 0.75 * thermal_margin_factor),
        MIN_ANGULAR_SPEED_RAD_S,
        MAX_ANGULAR_SPEED_RAD_S,
    )
    axial_feed = _clip(
        NOMINAL_AXIAL_FEED_M_S
        * pressure_factor
        * density_factor
        * (0.35 + 0.65 * thermal_margin_factor),
        0.0,
        MAX_AXIAL_FEED_M_S,
    )

    # Les composantes sont des corrections signées et faibles. Elles sont
    # déterministes tant que les entrées le sont et restent bornées à 10 % de
    # l'avance nominale afin de ne pas transformer le proxy en commande brutale.
    density_error = _clip(
        (density - REFERENCE_DENSITY_KG_M3) / REFERENCE_DENSITY_KG_M3,
        -1.0,
        1.0,
    )
    thermal_bias = _clip(
        (temp - AMBIENT_TEMPERATURE_C) / REFERENCE_TEMP_MARGIN_C,
        -1.0,
        2.0,
    )
    drift_scale = 0.10 * max(axial_feed, NOMINAL_AXIAL_FEED_M_S * 0.1)
    drift = (
        drift_scale * density_error,
        -drift_scale * thermal_bias * pressure_factor,
        drift_scale * (1.0 - pressure_factor),
    )

    coolant_flow = _clip(
        NOMINAL_COOLANT_FLOW_KG_S
        * (1.0 + 2.5 * (1.0 - thermal_margin_factor))
        * (1.0 + min(pressure_gpa / 400.0, 1.0)),
        0.0,
        MAX_COOLANT_FLOW_KG_S,
    )
    return DriftSolution(
        temperature_c=float(temp),
        pressure_pa=float(pressure),
        density_kg_m3=float(density),
        pressure_gpa=float(pressure_gpa),
        critical_temperature_c=float(critical),
        angular_speed_rad_s=float(angular_speed),
        coolant_flow_kg_s=float(coolant_flow),
        axial_feed_m_s=float(axial_feed),
        drift_vector_m_s=tuple(float(value) for value in drift),
        thermal_lock=False,
        cooldown_required=False,
        thermal_shield_active=False,
        lock_reason="aucun verrou thermique",
    )


__all__ = [
    "DriftSolution",
    "ThermalLockConfig",
    "ThermalLockController",
    "solve_drift_vectors",
]
