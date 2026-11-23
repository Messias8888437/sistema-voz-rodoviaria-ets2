import re
import unicodedata

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
