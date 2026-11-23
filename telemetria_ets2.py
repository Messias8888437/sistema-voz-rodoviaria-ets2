import ctypes
import re
import struct
import sys
import time
import unicodedata
from dataclasses import dataclass
from ctypes import wintypes
from typing import Any

SCS_SHARED_MEMORY_NAME = "Local\\SHSCSTelemetry"
SCS_SHARED_MEMORY_SIZE = 32 * 1024
GAME_TIME_OFFSET = 64
UPDATE_TIMESTAMP_OFFSET = 8
JOB_START_TIME_OFFSET = 444
CARGO_OFFSET = 2620
CITY_DESTINATION_OFFSET = 2748
CITY_SOURCE_OFFSET = 3004
ON_JOB_OFFSET = 4300
TELEMETRY_DATA_SIZE = ON_JOB_OFFSET + 1
TELEMETRY_STALE_SECONDS = 5.0
FILE_MAP_READ = 0x0004
ERROR_FILE_NOT_FOUND = 2
ERROR_PATH_NOT_FOUND = 3


@dataclass(frozen=True)
class TelemetrySnapshot:
    update_timestamp: int
    game_minutes: int
    job_start_time: int
    cargo: str
    city_source: str
    city_destination: str
    on_job: bool

    @property
    def game_time(self) -> str:
        minutes = self.game_minutes % (24 * 60)
        hour, minute = divmod(minutes, 60)
        if minute:
            return f"{hour} horas e {minute:02d} minutos"
        return f"{hour} horas"


def _decode_shared_string(data: bytes, offset: int) -> str:
    value = data[offset:offset + 64].split(b"\0", 1)[0]
    return value.decode("utf-8", errors="replace").strip()


def parse_shared_memory(data: bytes) -> TelemetrySnapshot:
    if len(data) < TELEMETRY_DATA_SIZE:
        raise ValueError(
            f"Bloco de telemetria incompleto: {len(data)} bytes; "
            f"mínimo esperado {TELEMETRY_DATA_SIZE}."
        )
    if not data[0]:
        raise ValueError("O plugin SCS ainda não ativou a telemetria do ETS2.")
    update_timestamp = struct.unpack_from("<Q", data, UPDATE_TIMESTAMP_OFFSET)[0]
    game_minutes = struct.unpack_from("<I", data, GAME_TIME_OFFSET)[0]
    job_start_time = struct.unpack_from("<I", data, JOB_START_TIME_OFFSET)[0]
    return TelemetrySnapshot(
        update_timestamp=update_timestamp,
        game_minutes=game_minutes,
        job_start_time=job_start_time,
        cargo=_decode_shared_string(data, CARGO_OFFSET),
        city_destination=_decode_shared_string(data, CITY_DESTINATION_OFFSET),
        city_source=_decode_shared_string(data, CITY_SOURCE_OFFSET),
        on_job=bool(data[ON_JOB_OFFSET]),
    )


class TelemetryReader:
    def __init__(self) -> None:
        self._kernel32: Any = None
        self._mapping = None
        self._view = None
        self._last_timestamp: int | None = None
        self._last_timestamp_change: float | None = None

    def _open(self) -> bool:
        if self._view:
            return True
        if sys.platform != "win32":
            raise OSError("A leitura do plugin SCS está disponível somente no Windows.")

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenFileMappingW.argtypes = (
            wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR,
        )
        kernel32.OpenFileMappingW.restype = wintypes.HANDLE
        kernel32.MapViewOfFile.argtypes = (
            wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
            wintypes.DWORD, ctypes.c_size_t,
        )
        kernel32.MapViewOfFile.restype = ctypes.c_void_p
        kernel32.UnmapViewOfFile.argtypes = (ctypes.c_void_p,)
        kernel32.UnmapViewOfFile.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL

        mapping = kernel32.OpenFileMappingW(
            FILE_MAP_READ, False, SCS_SHARED_MEMORY_NAME,
        )
        if not mapping:
            error = ctypes.get_last_error()
            if error in (ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND):
                return False
            raise ctypes.WinError(error)
        view = kernel32.MapViewOfFile(
            mapping, FILE_MAP_READ, 0, 0, SCS_SHARED_MEMORY_SIZE,
        )
        if not view:
            error = ctypes.get_last_error()
            kernel32.CloseHandle(mapping)
            raise ctypes.WinError(error)
        self._kernel32 = kernel32
        self._mapping = mapping
        self._view = view
        return True

    def read(self) -> TelemetrySnapshot | None:
        if not self._open():
            return None
        data = ctypes.string_at(self._view, TELEMETRY_DATA_SIZE)
        if not data[0]:
            self.close()
            return None
        snapshot = parse_shared_memory(data)
        now = time.monotonic()
        if snapshot.update_timestamp != self._last_timestamp:
            self._last_timestamp = snapshot.update_timestamp
            self._last_timestamp_change = now
        elif (
            self._last_timestamp_change is not None
            and now - self._last_timestamp_change >= TELEMETRY_STALE_SECONDS
        ):
            self.close()
            return None
        return snapshot

    def close(self) -> None:
        if self._kernel32 is None:
            return
        if self._view:
            self._kernel32.UnmapViewOfFile(self._view)
        if self._mapping:
            self._kernel32.CloseHandle(self._mapping)
        self._view = None
        self._mapping = None
        self._kernel32 = None
        self._last_timestamp = None
        self._last_timestamp_change = None

UFS_BRASIL = (
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
)
_SUFIXO_UF = re.compile(
    r"(?:\s*[,/_-]\s*|\s*\(\s*|\s+)(?:"
    + "|".join(UFS_BRASIL)
    + r")\s*\)?\s*$",
    re.IGNORECASE,
)

CIDADES_BRASILEIRAS = (
    "São Paulo", "Rio de Janeiro", "Belo Horizonte", "Vitória", "Curitiba",
    "Florianópolis", "Porto Alegre", "Brasília", "Goiânia", "Cuiabá",
    "Campo Grande", "Manaus", "Belém", "Macapá", "Boa Vista", "Porto Velho",
    "Rio Branco", "Palmas", "São Luís", "Teresina", "Fortaleza", "Natal",
    "João Pessoa", "Recife", "Maceió", "Aracaju", "Salvador",
    "Campinas", "Ribeirão Preto", "Santos", "São José dos Campos",
    "São José do Rio Preto", "Sorocaba", "Bauru", "Marília", "Araçatuba",
    "Presidente Prudente", "Piracicaba", "Franca", "Araraquara", "São Carlos",
    "Taubaté", "Guarulhos", "Osasco", "Jundiaí", "Barueri", "Limeira",
    "Rio Claro", "Botucatu", "Itapetininga", "Avaré", "Registro", "Juquiá",
    "Pariquera-Açu", "Cananéia", "Apiaí", "Capão Bonito",
    "São Lourenço da Serra", "Jacupiranga", "Eldorado", "Sete Barras",
    "Itanhaém", "Peruíbe", "Mongaguá", "Praia Grande", "São Vicente",
    "Guarujá", "Cubatão",
    "Londrina", "Maringá", "Ponta Grossa", "Cascavel", "Foz do Iguaçu",
    "Guarapuava", "Paranaguá", "Apucarana", "Campo Mourão", "Umuarama",
    "Toledo", "Joinville", "Blumenau", "Chapecó", "Criciúma", "Itajaí",
    "Lages", "Balneário Camboriú", "São Bento do Sul", "Caxias do Sul",
    "Pelotas", "Santa Maria", "Passo Fundo", "Uruguaiana", "Novo Hamburgo",
    "Canoas", "Uberlândia", "Juiz de Fora", "Contagem", "Betim",
    "Montes Claros", "Uberaba", "Governador Valadares", "Ipatinga",
    "Divinópolis", "Poços de Caldas", "Varginha", "Niterói",
    "Campos dos Goytacazes", "Petrópolis", "Volta Redonda", "Macaé",
    "Feira de Santana", "Vitória da Conquista", "Ilhéus", "Itabuna",
    "Porto Seguro", "Anápolis", "Rio Verde", "Catalão", "Jataí", "Dourados",
    "Três Lagoas", "Corumbá", "Rondonópolis", "Sinop", "Tangará da Serra",
    "Lucas do Rio Verde", "Santarém", "Marabá", "Parauapebas", "Altamira",
    "Cachoeiro de Itapemirim", "Colatina", "Linhares", "Pouso Alegre",
    "Patos de Minas", "Barreiras", "Juazeiro", "Crato", "Sobral",
    "Caruaru", "Petrolina", "Campina Grande", "Mossoró", "Imperatriz",
    "Caxias", "Aparecida de Goiânia", "Várzea Grande", "Arapongas",
    "Francisco Beltrão", "Erechim", "Santa Cruz do Sul", "Bagé",
    "Rio Grande", "Cachoeirinha", "Alvorada",
)


def _chave_cidade(texto: str) -> str:
    sem_acentos = unicodedata.normalize("NFKD", texto).casefold()
    sem_acentos = "".join(
        caractere for caractere in sem_acentos
        if not unicodedata.combining(caractere)
    )
    return re.sub(r"[^a-z0-9]+", " ", sem_acentos).strip()


_CIDADES_CANONICAS = {
    _chave_cidade(cidade): cidade for cidade in CIDADES_BRASILEIRAS
}


def limpar_cidade(cidade: str | None) -> str:
    texto = (cidade or "").strip()
    texto = _SUFIXO_UF.sub("", texto)
    texto = re.sub(r"[_\-\u2013\u2014]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    if not texto:
        return ""
    return _CIDADES_CANONICAS.get(_chave_cidade(texto), texto)


def detectar_modo(cargo: str | None) -> str:
    texto = unicodedata.normalize("NFKD", cargo or "").casefold()
    texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    palavras_leiteiras = ("leite", "milk", "laticin", "queijo", "iogurte", "tanque")
    if any(palavra in texto for palavra in palavras_leiteiras):
        return "leiteiro"
    return "rodoviaria"
