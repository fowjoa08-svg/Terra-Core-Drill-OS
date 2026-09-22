"""
TERRA-CORE-DRILL — registre de capteurs géophysiques en flux.

Le module définit un petit protocole binaire documenté et un registre de
traitement borné pour trois familles de capteurs :

* magnétométrie du noyau externe liquide fer-nickel ;
* pression piézoélectrique ;
* spectroscopie des silicates du manteau.

L'implémentation est conçue pour le traitement par flux : les statistiques sont
mises à jour par l'algorithme en ligne de Welford et l'historique conservé est
une deque de longueur maximale. Aucun dictionnaire de télémétrie non borné ne
s'accumule au fil du forage.

Protocole TLM1
--------------
En-tête little-endian ``<4sBBHIQ`` :

* magic ``b"TLM1"`` (4 octets) ;
* type de capteur (1 octet) ;
* version (1 octet, actuellement 1) ;
* taille de charge utile (uint16) ;
* numéro de séquence (uint32) ;
* timestamp en millisecondes (uint64).

Charges utiles :

* magnétomètre : ``<fffff`` = Bx, By, Bz en teslas, température en °C,
  conductivité électrique en S/m ;
* pression : ``<ff`` = pression en Pa et tension piézo en V ;
* spectromètre : ``<H`` puis ``N`` paires ``<ff`` (longueur d'onde en nm,
  intensité normalisée). N est plafonné pour préserver la mémoire.

Ce protocole est un contrat logiciel de démonstration ; une qualification
instrumentale réelle devra remplacer les facteurs de calibration.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import json
import math
import struct
from typing import Any, Deque, Dict, Iterable, Mapping, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# Protocole et modèles de données
# ---------------------------------------------------------------------------

MAGNETOMETER = 1
PIEZOELECTRIC_PRESSURE = 2
SILICATE_SPECTROMETER = 3
SUPPORTED_SENSOR_TYPES = frozenset(
    (MAGNETOMETER, PIEZOELECTRIC_PRESSURE, SILICATE_SPECTROMETER)
)
PROTOCOL_MAGIC = b"TLM1"
PROTOCOL_VERSION = 1
HEADER_STRUCT = struct.Struct("<4sBBHIQ")
MAGNETOMETER_STRUCT = struct.Struct("<fffff")
PRESSURE_STRUCT = struct.Struct("<ff")
SPECTRUM_COUNT_STRUCT = struct.Struct("<H")
SPECTRUM_POINT_STRUCT = struct.Struct("<ff")
MAX_SPECTRUM_BINS = 4_096


@dataclass(frozen=True)
class TelemetryHeader:
    """En-tête décodé, conservé séparément du signal physique."""

    sensor_type: int
    version: int
    payload_length: int
    sequence: int
    timestamp_ms: int


@dataclass(frozen=True)
class MagnetometerSample:
    """Mesure tri-axiale et proxy de convection du noyau externe."""

    timestamp_ms: int
    sequence: int
    bx_t: float
    by_t: float
    bz_t: float
    temperature_c: float
    conductivity_s_m: float
    field_magnitude_t: float
    convection_proxy: float


@dataclass(frozen=True)
class PiezoPressureSample:
    """Mesure de pression calibrée par capteur piézoélectrique."""

    timestamp_ms: int
    sequence: int
    pressure_pa: float
    voltage_v: float
    pressure_gpa: float


@dataclass(frozen=True)
class SilicateSpectrum:
    """Spectre borné et indices minéralogiques heuristiques."""

    timestamp_ms: int
    sequence: int
    wavelengths_nm: Tuple[float, ...]
    intensities: Tuple[float, ...]
    dominant_band_nm: Optional[float]
    olivine_index: float
    pyroxene_index: float
    feldspar_index: float


@dataclass(frozen=True)
class DecodedTelemetry:
    """Enveloppe uniforme retournée par ``decode_frame``."""

    header: TelemetryHeader
    sample: Union[MagnetometerSample, PiezoPressureSample, SilicateSpectrum]


@dataclass
class OnlineStatistics:
    """Moyenne, variance et extrêmes sans conserver les observations."""

    count: int = 0
    mean: float = 0.0
    m2: float = 0.0
    minimum: float = math.inf
    maximum: float = -math.inf

    def update(self, value: float) -> None:
        value = float(value)
        if not math.isfinite(value):
            return
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2
        self.minimum = min(self.minimum, value)
        self.maximum = max(self.maximum, value)

    @property
    def variance(self) -> float:
        return self.m2 / (self.count - 1) if self.count > 1 else 0.0

    @property
    def standard_deviation(self) -> float:
        return math.sqrt(max(0.0, self.variance))

    def as_dict(self) -> Dict[str, float]:
        return {
            "count": self.count,
            "mean": self.mean if self.count else 0.0,
            "variance": self.variance,
            "standard_deviation": self.standard_deviation,
            "minimum": self.minimum if self.count else 0.0,
            "maximum": self.maximum if self.count else 0.0,
        }


# ---------------------------------------------------------------------------
# Décodage des trames
# ---------------------------------------------------------------------------


def _validate_finite(values: Iterable[float], name: str) -> None:
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError(f"{name} contient une valeur non finie")


def _decode_magnetometer(
    payload: memoryview, header: TelemetryHeader
) -> MagnetometerSample:
    if len(payload) != MAGNETOMETER_STRUCT.size:
        raise ValueError("taille de charge utile magnétomètre incorrecte")
    bx, by, bz, temperature_c, conductivity = MAGNETOMETER_STRUCT.unpack(payload)
    _validate_finite((bx, by, bz, temperature_c, conductivity), "magnétomètre")
    if conductivity < 0.0:
        raise ValueError("la conductivité ne peut pas être négative")
    magnitude = math.sqrt(bx * bx + by * by + bz * bz)
    # Proxy de convection : produit dimensionnellement explicite servant à
    # classer les régimes, pas une inversion de la MHD du noyau.
    convection_proxy = magnitude * conductivity
    return MagnetometerSample(
        timestamp_ms=header.timestamp_ms,
        sequence=header.sequence,
        bx_t=bx,
        by_t=by,
        bz_t=bz,
        temperature_c=temperature_c,
        conductivity_s_m=conductivity,
        field_magnitude_t=magnitude,
        convection_proxy=convection_proxy,
    )


def _decode_pressure(
    payload: memoryview, header: TelemetryHeader
) -> PiezoPressureSample:
    if len(payload) != PRESSURE_STRUCT.size:
        raise ValueError("taille de charge utile pression incorrecte")
    pressure_pa, voltage_v = PRESSURE_STRUCT.unpack(payload)
    _validate_finite((pressure_pa, voltage_v), "pression")
    if pressure_pa < 0.0:
        raise ValueError("la pression ne peut pas être négative")
    return PiezoPressureSample(
        timestamp_ms=header.timestamp_ms,
        sequence=header.sequence,
        pressure_pa=pressure_pa,
        voltage_v=voltage_v,
        pressure_gpa=pressure_pa / 1.0e9,
    )


def _silicate_indices(
    wavelengths: Tuple[float, ...], intensities: Tuple[float, ...]
) -> Tuple[Optional[float], float, float, float]:
    """Calcule trois indices de bande simples sur flux déjà borné."""

    if not intensities:
        return None, 0.0, 0.0, 0.0
    peak_index = max(range(len(intensities)), key=intensities.__getitem__)
    dominant = wavelengths[peak_index]
    maximum = max(intensities)
    if maximum <= 0.0:
        return dominant, 0.0, 0.0, 0.0

    def band_score(low_nm: float, high_nm: float) -> float:
        values = [
            intensity
            for wavelength, intensity in zip(wavelengths, intensities)
            if low_nm <= wavelength <= high_nm
        ]
        return max(values, default=0.0) / maximum

    # Fenêtres indicatives : le registre expose des scores pour le contrôle,
    # non une identification minéralogique certifiée.
    return (
        dominant,
        band_score(1_000.0, 1_100.0),  # olivine, bande d'absorption indicative
        band_score(900.0, 1_000.0),  # pyroxène
        band_score(1_200.0, 1_300.0),  # feldspath
    )


def _decode_spectrum(
    payload: memoryview, header: TelemetryHeader
) -> SilicateSpectrum:
    if len(payload) < SPECTRUM_COUNT_STRUCT.size:
        raise ValueError("charge utile spectromètre trop courte")
    (count,) = SPECTRUM_COUNT_STRUCT.unpack_from(payload, 0)
    if count > MAX_SPECTRUM_BINS:
        raise ValueError("nombre de bandes spectrales au-delà de la limite")
    expected = SPECTRUM_COUNT_STRUCT.size + count * SPECTRUM_POINT_STRUCT.size
    if len(payload) != expected:
        raise ValueError("taille de charge utile spectromètre incorrecte")

    wavelengths = []
    intensities = []
    offset = SPECTRUM_COUNT_STRUCT.size
    for _ in range(count):
        wavelength, intensity = SPECTRUM_POINT_STRUCT.unpack_from(payload, offset)
        offset += SPECTRUM_POINT_STRUCT.size
        if not math.isfinite(wavelength) or not math.isfinite(intensity):
            raise ValueError("spectre contenant une valeur non finie")
        if wavelength < 0.0 or intensity < 0.0:
            raise ValueError("spectre contenant une valeur négative")
        wavelengths.append(float(wavelength))
        intensities.append(float(intensity))

    wavelength_tuple = tuple(wavelengths)
    intensity_tuple = tuple(intensities)
    dominant, olivine, pyroxene, feldspar = _silicate_indices(
        wavelength_tuple, intensity_tuple
    )
    return SilicateSpectrum(
        timestamp_ms=header.timestamp_ms,
        sequence=header.sequence,
        wavelengths_nm=wavelength_tuple,
        intensities=intensity_tuple,
        dominant_band_nm=dominant,
        olivine_index=olivine,
        pyroxene_index=pyroxene,
        feldspar_index=feldspar,
    )


def decode_frame(frame: bytes) -> DecodedTelemetry:
    """Valide puis décode une trame binaire TLM1.

    La fonction refuse silencieusement les trames tronquées ? Non : les erreurs
    de protocole sont levées explicitement afin que le superviseur puisse
    compter une perte de télémétrie plutôt que d'intégrer une fausse mesure.
    """

    if not isinstance(frame, (bytes, bytearray, memoryview)):
        raise TypeError("frame doit être un buffer binaire")
    view = memoryview(frame)
    if len(view) < HEADER_STRUCT.size:
        raise ValueError("trame plus courte que l'en-tête TLM1")

    magic, sensor_type, version, payload_length, sequence, timestamp_ms = (
        HEADER_STRUCT.unpack_from(view, 0)
    )
    if magic != PROTOCOL_MAGIC:
        raise ValueError("magic TLM1 invalide")
    if version != PROTOCOL_VERSION:
        raise ValueError(f"version TLM1 non supportée: {version}")
    if sensor_type not in SUPPORTED_SENSOR_TYPES:
        raise ValueError(f"type de capteur inconnu: {sensor_type}")

    expected_length = HEADER_STRUCT.size + payload_length
    if len(view) != expected_length:
        raise ValueError("longueur de trame incohérente")

    header = TelemetryHeader(
        sensor_type=sensor_type,
        version=version,
        payload_length=payload_length,
        sequence=sequence,
        timestamp_ms=timestamp_ms,
    )
    payload = view[HEADER_STRUCT.size:]
    if sensor_type == MAGNETOMETER:
        sample = _decode_magnetometer(payload, header)
    elif sensor_type == PIEZOELECTRIC_PRESSURE:
        sample = _decode_pressure(payload, header)
    else:
        sample = _decode_spectrum(payload, header)
    return DecodedTelemetry(header=header, sample=sample)


def encode_frame(
    sensor_type: int,
    sequence: int,
    timestamp_ms: int,
    payload: bytes,
    version: int = PROTOCOL_VERSION,
) -> bytes:
    """Construit une trame TLM1, principalement utile aux bancs de test."""

    if sensor_type not in SUPPORTED_SENSOR_TYPES:
        raise ValueError("sensor_type inconnu")
    if not 0 <= sequence <= 0xFFFFFFFF:
        raise ValueError("sequence hors uint32")
    if not 0 <= timestamp_ms <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("timestamp hors uint64")
    if len(payload) > 0xFFFF:
        raise ValueError("charge utile trop grande pour uint16")
    return HEADER_STRUCT.pack(
        PROTOCOL_MAGIC,
        sensor_type,
        version,
        len(payload),
        sequence,
        timestamp_ms,
    ) + bytes(payload)


# ---------------------------------------------------------------------------
# Registre et agrégations bornées
# ---------------------------------------------------------------------------


class SensorRegistry:
    """Registre de capteurs à historique limité et statistiques en ligne."""

    def __init__(self, history_limit: int = 256) -> None:
        if history_limit <= 0:
            raise ValueError("history_limit doit être positif")
        self.history_limit = int(history_limit)
        self._history: Deque[Dict[str, Any]] = deque(maxlen=self.history_limit)
        self._stats: Dict[str, OnlineStatistics] = {
            "field_magnitude_t": OnlineStatistics(),
            "convection_proxy": OnlineStatistics(),
            "pressure_pa": OnlineStatistics(),
            "spectral_olivine_index": OnlineStatistics(),
            "spectral_pyroxene_index": OnlineStatistics(),
            "spectral_feldspar_index": OnlineStatistics(),
        }
        self.frames_ingested = 0
        self.frames_rejected = 0
        self.last_sequence: Optional[int] = None

    def ingest(self, frame: bytes) -> DecodedTelemetry:
        """Décode et agrège une trame. Les erreurs sont comptées puis relancées."""

        try:
            decoded = decode_frame(frame)
        except (TypeError, ValueError):
            self.frames_rejected += 1
            raise

        self.frames_ingested += 1
        self.last_sequence = decoded.header.sequence
        sample = decoded.sample
        if isinstance(sample, MagnetometerSample):
            self._stats["field_magnitude_t"].update(sample.field_magnitude_t)
            self._stats["convection_proxy"].update(sample.convection_proxy)
            summary = {
                "type": "magnetometer",
                "sequence": sample.sequence,
                "timestamp_ms": sample.timestamp_ms,
                "field_magnitude_t": sample.field_magnitude_t,
                "convection_proxy": sample.convection_proxy,
            }
        elif isinstance(sample, PiezoPressureSample):
            self._stats["pressure_pa"].update(sample.pressure_pa)
            summary = {
                "type": "piezo_pressure",
                "sequence": sample.sequence,
                "timestamp_ms": sample.timestamp_ms,
                "pressure_pa": sample.pressure_pa,
                "pressure_gpa": sample.pressure_gpa,
            }
        else:
            self._stats["spectral_olivine_index"].update(sample.olivine_index)
            self._stats["spectral_pyroxene_index"].update(sample.pyroxene_index)
            self._stats["spectral_feldspar_index"].update(sample.feldspar_index)
            summary = {
                "type": "silicate_spectrum",
                "sequence": sample.sequence,
                "timestamp_ms": sample.timestamp_ms,
                "bins": len(sample.wavelengths_nm),
                "dominant_band_nm": sample.dominant_band_nm,
                "olivine_index": sample.olivine_index,
                "pyroxene_index": sample.pyroxene_index,
                "feldspar_index": sample.feldspar_index,
            }
        self._history.append(summary)
        return decoded

    def snapshot(self) -> Dict[str, Any]:
        """Retourne un état JSON-compatible sans exposer les objets internes."""

        return {
            "frames_ingested": self.frames_ingested,
            "frames_rejected": self.frames_rejected,
            "last_sequence": self.last_sequence,
            "history_limit": self.history_limit,
            "recent": list(self._history),
            "statistics": {
                name: stats.as_dict() for name, stats in self._stats.items()
            },
        }

    def snapshot_json(self, indent: Optional[int] = None) -> str:
        """Sérialise l'état courant pour un log ou un checkpoint."""

        return json.dumps(self.snapshot(), indent=indent, ensure_ascii=False)


__all__ = [
    "DecodedTelemetry",
    "MAGNETOMETER",
    "MagnetometerSample",
    "OnlineStatistics",
    "PIEZOELECTRIC_PRESSURE",
    "PiezoPressureSample",
    "SILICATE_SPECTROMETER",
    "SensorRegistry",
    "SilicateSpectrum",
    "TelemetryHeader",
    "decode_frame",
    "encode_frame",
]
