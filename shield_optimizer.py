"""
TERRA-CORE-DRILL — Optimisation du blindage thermique et mécanique.

Ce module fournit une implémentation déterministe et bornée en mémoire du modèle
simplifié d'un blindage en tungstène. Il ne prétend pas valider la faisabilité
physique d'un forage terrestre réel : les lois de contrôle et les profils de
matière sont des modèles d'ingénierie paramétriques destinés à l'architecture
logicielle et aux essais de pipeline.

Principes d'implémentation
--------------------------
* La géométrie n'est jamais matérialisée dans son intégralité. La fonction
  ``iter_honeycomb_blocks`` produit des blocs NumPy de taille bornée puis les
  libère au tour suivant. La mémoire de travail est donc O(taille_bloc),
  indépendante de la taille totale de la grille.
* La densité est intégrée par sommes scalaires en ligne ; aucun tableau global
  n'est conservé.
* Le transfert thermique utilise la solution en série de Fourier d'une plaque
  1-D à température imposée sur ses deux faces. Cette solution évite une boucle
  temporelle potentiellement longue tout en restant une résolution de
  l'équation \u2202T/\u2202t = \u03b1\u2202\u00b2T/\u2202x\u00b2.
* Toutes les conversions d'unités sont explicites. Les températures sont en
  degrés Celsius pour la télémétrie, les écarts thermiques étant identiques en
  kelvins.

Dépendance : NumPy uniquement.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Dict, Iterator, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Constantes matériaux et limites de calcul
# ---------------------------------------------------------------------------

TUNGSTEN_DENSITY_G_CM3 = 19.25
TARGET_SHIELD_DENSITY_G_CM3 = 3.85
TARGET_DENSITY_RATIO = TARGET_SHIELD_DENSITY_G_CM3 / TUNGSTEN_DENSITY_G_CM3
TUNGSTEN_DENSITY_KG_M3 = TUNGSTEN_DENSITY_G_CM3 * 1_000.0

# Valeurs thermiques représentatives du tungstène. Elles sont regroupées ici
# pour qu'un banc d'essai puisse les remplacer par une base matériaux qualifiée.
TUNGSTEN_CONDUCTIVITY_W_MK = 173.0
TUNGSTEN_SPECIFIC_HEAT_J_KGK = 134.0
TUNGSTEN_THERMAL_DIFFUSIVITY_M2_S = 6.70e-5

DEFAULT_LAYER_COUNT = 10
DEFAULT_GRID_SHAPE = (1_024, 1_024)
DEFAULT_BLOCK_SHAPE = (128, 128)
DEFAULT_FOURIER_TERMS = 256
MAX_FOURIER_TERMS = 4_096
SQRT3 = math.sqrt(3.0)


@dataclass(frozen=True)
class HoneycombSpec:
    """Paramètres de la maille hexagonale rasterisée.

    ``cell_pitch_nm`` et ``wall_thickness_nm`` définissent la géométrie
    physique. ``pixels_per_cell`` ne change pas l'échelle physique ; il fixe la
    résolution numérique locale et permet de contrôler la mémoire par bloc.
    """

    cell_pitch_nm: float = 100.0
    # 7.42 nm donne une fraction solide d'environ 20 % à la résolution par
    # défaut, donc une densité raster pratiquement égale à la cible 3.85 g/cm³.
    wall_thickness_nm: float = 7.42
    perforation_radius_fraction: float = 0.08
    pixels_per_cell: int = 64

    def __post_init__(self) -> None:
        if self.cell_pitch_nm <= 0.0:
            raise ValueError("cell_pitch_nm doit être strictement positif")
        if self.wall_thickness_nm <= 0.0:
            raise ValueError("wall_thickness_nm doit être strictement positif")
        if self.wall_thickness_nm >= self.cell_pitch_nm / 2.0:
            raise ValueError(
                "l'épaisseur de paroi doit rester inférieure à la demi-maille"
            )
        if not 0.0 <= self.perforation_radius_fraction <= 1.0:
            raise ValueError("perforation_radius_fraction doit être dans [0, 1]")
        if self.pixels_per_cell < 8:
            raise ValueError("pixels_per_cell doit être >= 8 pour rasteriser l'hexagone")


@dataclass(frozen=True)
class FourierResult:
    """Résultat compact d'une résolution thermique de plaque 1-D."""

    initial_temperature_c: float
    boundary_temperature_c: float
    elapsed_s: float
    midplane_temperature_c: float
    surface_heat_flux_w_m2: float
    thermal_diffusivity_m2_s: float
    series_terms: int


@dataclass(frozen=True)
class ShieldOptimizationResult:
    """Résumé sérialisable de l'optimisation des dix couches."""

    layer_count: int
    nominal_density_g_cm3: float
    target_density_g_cm3: float
    modeled_solid_fraction: float
    modeled_density_g_cm3: float
    target_density_ratio: float
    mass_reduction_percent: float
    density_error_g_cm3: float
    cooldown_time_s: float
    temperature_after_cooldown_c: float
    peak_surface_heat_flux_w_m2: float
    thermal_diffusivity_m2_s: float
    geometry: HoneycombSpec
    thermal: FourierResult

    def to_dict(self) -> Dict[str, object]:
        """Retourne un dictionnaire prêt pour JSON ou Markdown."""

        result = asdict(self)
        result["geometry"] = asdict(self.geometry)
        result["thermal"] = asdict(self.thermal)
        return result


# ---------------------------------------------------------------------------
# Géométrie en nid d'abeille — génération par blocs
# ---------------------------------------------------------------------------


def _hex_distance(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Distance de jauge d'un hexagone régulier à sommet horizontal.

    Pour un rayon circonscrit unitaire, un point est dans l'hexagone lorsque
    cette distance est <= 1. La fonction est vectorisée et ne conserve pas
    d'état entre deux blocs.
    """

    return np.maximum(np.abs(x), 0.5 * np.abs(x) + (SQRT3 / 2.0) * np.abs(y))


def build_honeycomb_block(
    global_row: int,
    global_col: int,
    block_rows: int,
    block_cols: int,
    spec: HoneycombSpec = HoneycombSpec(),
    dtype: np.dtype = np.dtype(np.float32),
) -> np.ndarray:
    """Construit un bloc de fraction solide d'une géométrie hexagonale perforée.

    Parameters
    ----------
    global_row, global_col:
        Coordonnées du coin supérieur gauche dans la grille raster globale.
    block_rows, block_cols:
        Dimensions du bloc. Elles sont validées avant allocation.
    spec:
        Paramètres physiques et résolution de la maille.
    dtype:
        ``float32`` par défaut : suffisant pour une fraction de matière et deux
        fois moins de mémoire que ``float64``.

    Returns
    -------
    numpy.ndarray
        Matrice 2-D bornée contenant 0.0 pour le vide et 1.0 pour la matière.
        Les six perforations circulaires sont retirées des ligaments.

    Notes
    -----
    La matrice renvoyée est volontairement locale. Le code appelant doit la
    réduire immédiatement ou la transmettre au prochain étage de pipeline ;
    il ne faut pas concaténer les blocs.
    """

    if global_row < 0 or global_col < 0:
        raise ValueError("les coordonnées globales doivent être positives")
    if block_rows <= 0 or block_cols <= 0:
        raise ValueError("les dimensions d'un bloc doivent être positives")

    # Les vecteurs 1-D sont broadcastés en un seul bloc. Leur taille est
    # strictement celle demandée, donc la consommation est bornée.
    rows = np.arange(global_row, global_row + block_rows, dtype=np.float64)[:, None]
    cols = np.arange(global_col, global_col + block_cols, dtype=np.float64)[None, :]

    pitch_px = float(spec.pixels_per_cell)
    vertical_pitch_px = (SQRT3 / 2.0) * pitch_px

    # Centre du site hexagonal le plus proche pour chaque pixel. Le décalage
    # d'une demi-maille sur les lignes alternées forme le réseau en nid d'abeille.
    lattice_row = np.floor(rows / vertical_pitch_px + 0.5).astype(np.int64)
    parity = (lattice_row & 1).astype(np.float64)
    lattice_col = np.floor(cols / pitch_px - 0.5 * parity + 0.5).astype(np.int64)

    x = cols / pitch_px - (lattice_col + 0.5 * parity)
    y = rows / pitch_px - lattice_row * (SQRT3 / 2.0)

    outer_radius = 0.5
    wall_ratio = spec.wall_thickness_nm / spec.cell_pitch_nm
    inner_radius = max(0.0, outer_radius - wall_ratio)

    distance = _hex_distance(x, y)
    outer_hex = distance <= outer_radius
    inner_void = distance <= inner_radius

    # Matière = couronne périphérique du site hexagonal. Le reste du site est
    # l'alvéole ouverte ; le motif périodique est déjà implicite dans le choix
    # du centre le plus proche.
    solid = outer_hex & ~inner_void

    # Six micro-perforations réparties dans les ligaments. Leur rayon est
    # relatif à l'épaisseur de paroi, et non à la taille globale de la maille.
    hole_radius = (
        spec.perforation_radius_fraction * wall_ratio * 0.85
    )
    hole_center_radius = inner_radius + 0.5 * wall_ratio
    perforation = np.zeros_like(solid, dtype=bool)
    for angle in np.arange(0.0, 2.0 * math.pi, math.pi / 3.0):
        cx = hole_center_radius * math.cos(float(angle))
        cy = hole_center_radius * math.sin(float(angle))
        perforation |= (x - cx) ** 2 + (y - cy) ** 2 <= hole_radius**2

    solid &= ~perforation
    # astype(copy=False) conserve la limite mémoire et permet au caller de
    # choisir float16/float32 si un profil embarqué le requiert.
    return solid.astype(dtype, copy=False)


def iter_honeycomb_blocks(
    grid_shape: Tuple[int, int] = DEFAULT_GRID_SHAPE,
    spec: HoneycombSpec = HoneycombSpec(),
    block_shape: Tuple[int, int] = DEFAULT_BLOCK_SHAPE,
    alternate: bool = True,
) -> Iterator[np.ndarray]:
    """Itère sur la matrice logique par blocs alternés, sans matrice globale.

    L'ordre des colonnes est inversé un bloc de lignes sur deux lorsque
    ``alternate`` est vrai. Cette option permet d'exercer un ordonnanceur
    downstream qui ne doit pas supposer un ordre monotone, tout en gardant un
    accès spatial local et déterministe.
    """

    total_rows, total_cols = grid_shape
    block_rows, block_cols = block_shape
    if total_rows <= 0 or total_cols <= 0:
        raise ValueError("grid_shape doit contenir deux entiers positifs")
    if block_rows <= 0 or block_cols <= 0:
        raise ValueError("block_shape doit contenir deux entiers positifs")

    row_starts = range(0, total_rows, block_rows)
    col_starts = list(range(0, total_cols, block_cols))

    for row_index, row_start in enumerate(row_starts):
        starts = col_starts
        if alternate and row_index % 2:
            starts = reversed(col_starts)
        for col_start in starts:
            rows = min(block_rows, total_rows - row_start)
            cols = min(block_cols, total_cols - col_start)
            yield build_honeycomb_block(
                row_start,
                col_start,
                rows,
                cols,
                spec=spec,
            )


def integrate_solid_fraction(
    grid_shape: Tuple[int, int] = DEFAULT_GRID_SHAPE,
    spec: HoneycombSpec = HoneycombSpec(),
    block_shape: Tuple[int, int] = DEFAULT_BLOCK_SHAPE,
) -> float:
    """Intègre la fraction de matière en flux, avec un accumulateur scalaire."""

    total_solid = 0.0
    total_cells = 0
    for block in iter_honeycomb_blocks(grid_shape, spec, block_shape):
        total_solid += float(np.sum(block, dtype=np.float64))
        total_cells += int(block.size)
    if total_cells == 0:  # Défense redondante, grid_shape est déjà validé.
        raise RuntimeError("grille vide")
    return total_solid / float(total_cells)


def required_void_fraction(
    nominal_density_g_cm3: float = TUNGSTEN_DENSITY_G_CM3,
    target_density_g_cm3: float = TARGET_SHIELD_DENSITY_G_CM3,
) -> float:
    """Calcule la porosité nécessaire pour atteindre la densité cible."""

    if nominal_density_g_cm3 <= 0.0 or target_density_g_cm3 < 0.0:
        raise ValueError("densités invalides")
    if target_density_g_cm3 > nominal_density_g_cm3:
        raise ValueError("la cible ne peut pas dépasser la densité nominale")
    return 1.0 - target_density_g_cm3 / nominal_density_g_cm3


# ---------------------------------------------------------------------------
# Transfert thermique de Fourier
# ---------------------------------------------------------------------------


def _midplane_dimensionless_temperature(
    elapsed_s: float,
    thickness_m: float,
    diffusivity_m2_s: float,
    terms: int,
) -> float:
    """Série de Fourier sans dimension au plan médian de la plaque."""

    if elapsed_s <= 0.0:
        return 1.0
    n = np.arange(terms, dtype=np.float64)
    odd = 2.0 * n + 1.0
    signs = 1.0 - 2.0 * (n.astype(np.int64) & 1)
    exponent = -((odd * math.pi / thickness_m) ** 2) * diffusivity_m2_s * elapsed_s
    value = (4.0 / math.pi) * np.sum(signs * np.exp(exponent) / odd)
    return float(np.clip(value, 0.0, 1.0))


def solve_fourier_heat_transfer(
    initial_temperature_c: float = 5_500.0,
    boundary_temperature_c: float = 20.0,
    elapsed_s: float = 1.0,
    thickness_m: float = 0.10,
    conductivity_w_mk: float = TUNGSTEN_CONDUCTIVITY_W_MK,
    density_kg_m3: float = TARGET_SHIELD_DENSITY_G_CM3 * 1_000.0,
    specific_heat_j_kgk: float = TUNGSTEN_SPECIFIC_HEAT_J_KGK,
    terms: int = DEFAULT_FOURIER_TERMS,
) -> FourierResult:
    """Résout la dissipation thermique 1-D par série de Fourier.

    Le modèle suppose une plaque homogène, une température initiale uniforme et
    deux faces maintenues à ``boundary_temperature_c``. Le point médian est le
    point chaud conservatif pour la température résiduelle. Le flux de surface
    est calculé par dérivation de la même série.

    La série est tronquée à ``MAX_FOURIER_TERMS`` afin qu'une valeur utilisateur
    aberrante ne crée jamais une allocation non bornée.
    """

    if thickness_m <= 0.0:
        raise ValueError("thickness_m doit être positif")
    if conductivity_w_mk <= 0.0 or density_kg_m3 <= 0.0 or specific_heat_j_kgk <= 0.0:
        raise ValueError("les propriétés thermiques doivent être positives")
    if elapsed_s < 0.0:
        raise ValueError("elapsed_s ne peut pas être négatif")
    terms = max(8, min(int(terms), MAX_FOURIER_TERMS))

    diffusivity = conductivity_w_mk / (density_kg_m3 * specific_heat_j_kgk)
    theta = _midplane_dimensionless_temperature(
        elapsed_s, thickness_m, diffusivity, terms
    )
    midplane_temperature = boundary_temperature_c + (
        initial_temperature_c - boundary_temperature_c
    ) * theta

    # |q| = k |dT/dx| sur la face. À t=0, le gradient idéal d'une marche de
    # température est singulier ; inf est plus honnête qu'un faux zéro.
    if elapsed_s == 0.0:
        heat_flux = math.inf
    else:
        n = np.arange(terms, dtype=np.float64)
        odd = 2.0 * n + 1.0
        exponent = -((odd * math.pi / thickness_m) ** 2) * diffusivity * elapsed_s
        gradient_sum = float(np.sum(np.exp(exponent)))
        heat_flux = (
            conductivity_w_mk
            * abs(initial_temperature_c - boundary_temperature_c)
            * (4.0 / thickness_m)
            * gradient_sum
        )

    return FourierResult(
        initial_temperature_c=float(initial_temperature_c),
        boundary_temperature_c=float(boundary_temperature_c),
        elapsed_s=float(elapsed_s),
        midplane_temperature_c=float(midplane_temperature),
        surface_heat_flux_w_m2=float(heat_flux),
        thermal_diffusivity_m2_s=float(diffusivity),
        series_terms=terms,
    )


def estimate_fourier_cooldown_time(
    initial_temperature_c: float = 5_500.0,
    target_temperature_c: float = 1_000.0,
    boundary_temperature_c: float = 20.0,
    thickness_m: float = 0.10,
    conductivity_w_mk: float = TUNGSTEN_CONDUCTIVITY_W_MK,
    density_kg_m3: float = TARGET_SHIELD_DENSITY_G_CM3 * 1_000.0,
    specific_heat_j_kgk: float = TUNGSTEN_SPECIFIC_HEAT_J_KGK,
    terms: int = DEFAULT_FOURIER_TERMS,
    max_bracket_s: float = 7.0 * 24.0 * 3_600.0,
) -> float:
    """Estime par dichotomie le temps pour atteindre la température cible.

    La recherche est logarithmique puis binaire ; elle ne lance aucun thread et
    n'attend pas en temps réel. ``max_bracket_s`` protège le pipeline contre un
    cas de paramètres qui ne refroidirait pas suffisamment.
    """

    if initial_temperature_c <= target_temperature_c:
        return 0.0
    if target_temperature_c <= boundary_temperature_c:
        raise ValueError("la cible doit rester au-dessus de la température de bord")
    if max_bracket_s <= 0.0:
        raise ValueError("max_bracket_s doit être positif")

    def temperature_at(time_s: float) -> float:
        return solve_fourier_heat_transfer(
            initial_temperature_c=initial_temperature_c,
            boundary_temperature_c=boundary_temperature_c,
            elapsed_s=time_s,
            thickness_m=thickness_m,
            conductivity_w_mk=conductivity_w_mk,
            density_kg_m3=density_kg_m3,
            specific_heat_j_kgk=specific_heat_j_kgk,
            terms=terms,
        ).midplane_temperature_c

    low = 0.0
    high = 1.0
    while high < max_bracket_s and temperature_at(high) > target_temperature_c:
        high *= 2.0
    high = min(high, max_bracket_s)
    if temperature_at(high) > target_temperature_c:
        raise RuntimeError("la cible thermique n'est pas atteinte dans la fenêtre")

    for _ in range(60):
        middle = 0.5 * (low + high)
        if temperature_at(middle) > target_temperature_c:
            low = middle
        else:
            high = middle
    return high


# ---------------------------------------------------------------------------
# Façade d'optimisation utilisée par core_main.py
# ---------------------------------------------------------------------------


def optimize_shield(
    layer_count: int = DEFAULT_LAYER_COUNT,
    grid_shape: Tuple[int, int] = DEFAULT_GRID_SHAPE,
    block_shape: Tuple[int, int] = DEFAULT_BLOCK_SHAPE,
    spec: Optional[HoneycombSpec] = None,
    initial_temperature_c: float = 5_500.0,
    target_cooldown_temperature_c: float = 1_000.0,
    boundary_temperature_c: float = 20.0,
    slab_thickness_m: float = 0.10,
) -> ShieldOptimizationResult:
    """Exécute le calcul borné de densité et de dissipation du blindage.

    Les dix couches sont représentées dans le résultat de conception ; la
    géométrie d'une couche est intégrée une fois, car les couches homogènes ont
    le même motif. Une extension multi-matériaux peut remplacer ``spec`` sans
    modifier le contrat du pipeline.
    """

    if layer_count <= 0:
        raise ValueError("layer_count doit être positif")
    spec = spec or HoneycombSpec()

    solid_fraction = integrate_solid_fraction(grid_shape, spec, block_shape)
    modeled_density = TUNGSTEN_DENSITY_G_CM3 * solid_fraction
    mass_reduction = 100.0 * (1.0 - modeled_density / TUNGSTEN_DENSITY_G_CM3)

    density_kg_m3 = max(modeled_density, 1.0) * 1_000.0
    cooldown_s = estimate_fourier_cooldown_time(
        initial_temperature_c=initial_temperature_c,
        target_temperature_c=target_cooldown_temperature_c,
        boundary_temperature_c=boundary_temperature_c,
        thickness_m=slab_thickness_m,
        density_kg_m3=density_kg_m3,
    )
    thermal = solve_fourier_heat_transfer(
        initial_temperature_c=initial_temperature_c,
        boundary_temperature_c=boundary_temperature_c,
        elapsed_s=cooldown_s,
        thickness_m=slab_thickness_m,
        density_kg_m3=density_kg_m3,
    )

    return ShieldOptimizationResult(
        layer_count=int(layer_count),
        nominal_density_g_cm3=TUNGSTEN_DENSITY_G_CM3,
        target_density_g_cm3=TARGET_SHIELD_DENSITY_G_CM3,
        modeled_solid_fraction=float(solid_fraction),
        modeled_density_g_cm3=float(modeled_density),
        target_density_ratio=float(TARGET_DENSITY_RATIO),
        mass_reduction_percent=float(mass_reduction),
        density_error_g_cm3=float(modeled_density - TARGET_SHIELD_DENSITY_G_CM3),
        cooldown_time_s=float(cooldown_s),
        temperature_after_cooldown_c=float(thermal.midplane_temperature_c),
        peak_surface_heat_flux_w_m2=float(thermal.surface_heat_flux_w_m2),
        thermal_diffusivity_m2_s=float(thermal.thermal_diffusivity_m2_s),
        geometry=spec,
        thermal=thermal,
    )


__all__ = [
    "DEFAULT_BLOCK_SHAPE",
    "DEFAULT_GRID_SHAPE",
    "DEFAULT_LAYER_COUNT",
    "FourierResult",
    "HoneycombSpec",
    "ShieldOptimizationResult",
    "TARGET_DENSITY_RATIO",
    "TARGET_SHIELD_DENSITY_G_CM3",
    "TUNGSTEN_DENSITY_G_CM3",
    "build_honeycomb_block",
    "estimate_fourier_cooldown_time",
    "integrate_solid_fraction",
    "iter_honeycomb_blocks",
    "optimize_shield",
    "required_void_fraction",
    "solve_fourier_heat_transfer",
]
