# Sistema de Voz Rodoviária para ETS2

Aplicativo de anúncios de embarque em português para o **Euro Truck Simulator 2 1.62 com o Mapa EAA**. O painel permite informar a viagem, escolher a voz neural e ajustar o volume da locução, do áudio de fundo e da campainha. O script do SimHub pode iniciar o motor de anúncios quando um trabalho começa no jogo.

## Requisitos

- Windows e Python **3.15 ou superior**, com `tkinter` disponível.
- Pacotes Python `edge-tts` e `static-ffmpeg`.
- [SimHub](https://www.simhubdash.com/) para acionar anúncios a partir de eventos do jogo.
- PyInstaller, somente para gerar o executável do painel.

Instale as dependências em um terminal:

```powershell
py -3.15 -m pip install edge-tts static-ffmpeg pyinstaller
```

O projeto também usa `campainha.wav` e um áudio de fundo chamado `fundo_rodoviaria.wav` ou `fundo_rodoviaria.mp3`. Os dois áudios fornecidos estão incluídos no repositório. O aplicativo pode trocar o áudio de fundo por outro arquivo WAV ou MP3.

## Executar o painel

Na pasta do projeto:

```powershell
python app_rodoviaria.py
```

O painel salva preferências em `config_rodoviaria.json`. Ao disparar um anúncio, ele executa `falar_rodoviaria.py`, que gera a locução com edge-tts, mistura voz, campainha e áudio de fundo com FFmpeg e reproduz o resultado. O pacote `static-ffmpeg` disponibiliza FFmpeg/FFprobe; a locução requer conexão com o serviço edge-tts.

O motor também pode ser chamado diretamente:

```powershell
python falar_rodoviaria.py --origem "São Paulo" --destino "Campinas" --hora "19 horas" --plataforma "4"
```

## Compilar o painel

Instale o PyInstaller e compile a interface:

```powershell
py -3.15 -m PyInstaller --noconfirm --onefile --windowed --name CentralRodoviaria app_rodoviaria.py
```

O executável será criado em `dist\CentralRodoviaria.exe`. Para usá-lo, mantenha `falar_rodoviaria.py`, `config_rodoviaria.json`, `campainha.wav` e um dos arquivos de áudio de fundo ao lado do executável. Python 3.15 e as dependências `edge-tts` e `static-ffmpeg` também precisam estar instalados e acessíveis no PATH: o painel compilado continua iniciando o motor como um script Python separado.

## Integração com o SimHub

1. Abra as configurações de ações/eventos do SimHub e associe uma ação ao evento **`DataCorePlugin.GameData.JobStarted`**.
2. Configure a ação para executar o Python (`python.exe`) com os argumentos produzidos por `anuncio_rodoviaria.js`. O script retorna o caminho de `falar_rodoviaria.py` seguido dos parâmetros de origem, destino, horário do jogo e plataforma; adapte o método de execução ao tipo de ação disponível na sua versão do SimHub.
3. Antes de ativar a ação, edite em `anuncio_rodoviaria.js` a variável `script` para o caminho completo de `falar_rodoviaria.py` no seu computador. O valor incluído no arquivo aponta para `C:\Users\messi\Desktop\Sistema_Voz_ETS2\falar_rodoviaria.py`.
4. O SimHub e o jogo devem estar em execução. Ao iniciar um trabalho, o script lê as cidades e o horário do jogo, escolhe uma plataforma aleatória de 1 a 12 e monta os argumentos do anúncio.

O painel e o motor compartilham `config_rodoviaria.json`, portanto os ajustes de voz, volumes e eco também se aplicam aos anúncios acionados pelo SimHub.

## Arquivos principais

- `app_rodoviaria.py`: painel gráfico.
- `falar_rodoviaria.py`: geração, mixagem e reprodução dos anúncios.
- `gerar_audios.py`: geração dos arquivos WAV de campainha e fundo.
- `anuncio_rodoviaria.js`: montagem dos argumentos a partir dos dados do ETS2 no SimHub.
- `campainha.wav` e `fundo_rodoviaria.wav`: efeitos sonoros usados na mixagem.
