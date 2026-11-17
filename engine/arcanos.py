"""
CATÁLOGO DOS 22 ARCANOS MAIORES
================================
Fonte unica de verdade: numero, nome, elemento hermetico e ID no Google Drive.

O elemento aqui NAO e decorativo: cada arcano tem correspondencia astrologica
classica (Mercúrio, Lua, Vênus, Marte…), e o motor usa isso como direcao de arte.
Quando o arcano nao esta no catalogo, o analisador decide pela paleta.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Arcano:
    numero: int | str
    nome: str
    elemento: str          # fogo | agua | luz | terra | ar
    regente: str           # astro/planeta classico
    drive_id: str

    @property
    def arquivo_base(self) -> str:
        numero_txt = f"{self.numero:02d}" if isinstance(self.numero, int) else "00"
        return f"{numero_txt}_{self.nome.lower().replace(' ', '_').replace(chr(39), '')}"

    @property
    def titulo(self) -> str:
        if self.numero == 0:
            return self.nome
        return f"{self.nome}"

    @property
    def subtitulo(self) -> str:
        if self.numero == 0:
            return "ARCANO 0 · O LOUCO"
        romanos = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII",
                   9: "IX", 10: "X", 11: "XI", 12: "XII", 13: "XIII", 14: "XIV", 15: "XV",
                   16: "XVI", 17: "XVII", 18: "XVIII", 19: "XIX", 20: "XX", 21: "XXI"}
        r = romanos.get(self.numero, "")
        return f"ARCANO {r} · {self.regente.upper()}"


# Ordem do tarô de Marselha (Grimaud): Justice = VIII, Força = XI
ARCANOS: list[Arcano] = [
    Arcano(0,  "Le Mat",            "ar",    "Urano",    "1u056VmsEiw2jw3rWX9vTDNh_HRAMhocS"),
    Arcano(1,  "Le Bateleur",       "fogo",  "Mercúrio", "1mvX-9sjpCiJ7tulHwH7UylhUZdo0hLAz"),
    Arcano(2,  "La Papesse",        "agua",  "Lua",      "13-owBCg6HVWPp9DTKPKoiOwt3goLDAdm"),
    Arcano(3,  "L Imperatrice",     "terra", "Vênus",    "1Zbs1ATYnUlN81dxfSkHbfs0hfio7jy-S"),
    Arcano(4,  "L Empereur",        "fogo",  "Áries",    "1DrATNkZ7MPoIBp34QTByM32w4UKnET3j"),
    Arcano(5,  "Le Pape",           "terra", "Touro",    "1SBPaEcS8otS-w0Fb6l_1jtVSjvOqUnzB"),
    Arcano(6,  "L Amoureux",        "ar",    "Gêmeos",   "1vJeSUJRPW_asC78s0E-y7e7sXbzw96dA"),
    Arcano(7,  "Le Chariot",        "agua",  "Câncer",   "1dTs_PEGLRrAyS-C1HQR5O-xTz6j03lw_"),
    Arcano(8,  "La Justice",        "ar",    "Libra",    "1KOFt879U1VLoz6NiqI47okwp02qLupwg"),
    Arcano(9,  "L Ermite",          "terra", "Virgem",   "1w0F_axnJpdbI9qDMFbrzkOTxF7R139ka"),
    Arcano(10, "La Roue de Fortune", "fogo", "Júpiter",  "1UR2apwxzMXkzFUL-c9enG9ekDjDfP5JJ"),
    Arcano(11, "La Force",          "fogo",  "Leão",     "1DFmOHvwBVsmg-DLMbNZ_d_hL80YMbauh"),
    Arcano(12, "Le Pendu",          "agua",  "Netuno",   "1H3JWYic-9QxHv1MpiICuzYq9uxy7of7b"),
    Arcano(13, "L Arcane sans Nom", "agua",  "Escorpião", "1WZk-n207dj3VoRBsHyfc1NzoYbpBGSRd"),
    Arcano(14, "Temperance",        "fogo",  "Sagitário", "1z02eKNerM9q6CeuZ6LuEce3RBcidFHZg"),
    Arcano(15, "Le Diable",         "terra", "Capricórnio", "1nVaJihwHMBabQakgsDbwZ9zjGIiJ7Jof"),
    Arcano(16, "La Maison Dieu",    "fogo",  "Marte",    "1vSwJbqlabrMXixIss7qw959691_HB42R"),
    Arcano(17, "L Etoile",          "ar",    "Aquário",  "1-9oSxIbsweV9WHlc7ZO6HnFVJv1dQovt"),
    Arcano(18, "La Lune",           "agua",  "Peixes",   "1n2OZNnQzrSAfHiJXiKnczgotbtEKqz5o"),
    Arcano(19, "Le Soleil",         "luz",   "Sol",      "1sII92SbIqdIKUrqO3MhsTnozGVdoZ6jH"),
    Arcano(20, "Le Jugement",       "fogo",  "Plutão",   "1R3I2xmnWrOWWNur4yI-00P5b6guUWURS"),
    Arcano(21, "Le Monde",          "terra", "Saturno",  "1xbtm7y1NFwopp99rT8TcDQI5sYS3-E_9"),
]

POR_NUMERO = {a.numero: a for a in ARCANOS}
POR_NOME = {a.nome.upper(): a for a in ARCANOS}


def por_numero(n) -> Arcano | None:
    try:
        return POR_NUMERO.get(int(n))
    except (TypeError, ValueError):
        return None


def do_drive_id(fid: str) -> Arcano | None:
    for a in ARCANOS:
        if a.drive_id == fid:
            return a
    return None


def para_secrets() -> str:
    """gera o bloco ARCANOS_JSON pronto para colar no Streamlit Secrets"""
    linhas = ",\n".join(f'  "{a.numero} · {a.nome}": "{a.drive_id}"' for a in ARCANOS)
    return "ARCANOS_JSON = '{\n" + linhas.replace("'", "\\'") + "\n}'"


def listar() -> list[Arcano]:
    return list(ARCANOS)


if __name__ == "__main__":
    for a in ARCANOS:
        print(f"{str(a.numero):>2}  {a.nome:22s} {a.elemento:6s} {a.regente:12s} {a.drive_id}")
    print(f"\n{len(ARCANOS)} arcanos no catálogo")
