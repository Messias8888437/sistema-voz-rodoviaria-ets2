import unicodedata


def detectar_modo(cargo: str | None) -> str:
    texto = unicodedata.normalize("NFKD", cargo or "").casefold()
    texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    palavras_leiteiras = ("leite", "milk", "laticin", "queijo", "iogurte", "tanque")
    if any(palavra in texto for palavra in palavras_leiteiras):
        return "leiteiro"
    return "rodoviaria"
