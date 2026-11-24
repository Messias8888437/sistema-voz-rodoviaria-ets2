# Sistema de Voz Rodoviária para ETS2

Aplicativo em português para anúncios no **Euro Truck Simulator 2 1.62**, sem depender do SimHub em execução. A conexão direta lê a memória compartilhada `Local\SCSTelemetry`, publicada pelo plugin SCS `scs-telemetry.dll` (RenCloud) instalado no ETS2. A normalização de cidades foi preparada para nomes dos mapas brasileiros **Mapa Eldorado, Mapa EAA, Rotas Brasil e RBR**, além de outros mapas. O painel oferece os modos **Passageiros (Rodoviária)** e **Leiteiro (Coleta de Leite)**, além de controles de voz e volume.

## Requisitos

- Windows e Python **3.15 ou superior**, com `tkinter`.
- Pacotes Python `edge-tts` e `static-ffmpeg`.
- PyInstaller para compilar o executável.
- O plugin de telemetria `scs-telemetry.dll` (RenCloud), distribuído separadamente.

Instale as dependências:

```powershell
py -3.15 -m pip install edge-tts static-ffmpeg pyinstaller
```

## Instalar e conectar o plugin de telemetria

1. Feche o ETS2.
2. Na pasta de instalação do jogo, confirme que existe `bin\win_x64\plugins`. Por exemplo, em uma instalação Steam padrão:
   `C:\Program Files (x86)\Steam\steamapps\common\Euro Truck Simulator 2\bin\win_x64\plugins`
3. Instale o `scs-telemetry.dll` do plugin RenCloud nessa pasta. O plugin não é distribuído junto com este projeto.
4. Inicie o ETS2 e depois abra `RodoviariaETS2.exe`. O painel lê diretamente a memória compartilhada `Local\SCSTelemetry`, criada pelo plugin quando o jogo carrega. Não é necessário instalar `ETS2Telemetry_x64.dll` ou `SHEETS2Telemetry_x64.dll`, nem abrir o SimHub.

O status **Conexão direta com o ETS2** no painel mostra quando o plugin está publicando telemetria, se há um trabalho ativo, origem, destino, horário do jogo e carga. Enquanto estiver conectado, os campos do painel são atualizados com os dados do jogo. A opção **Anunciar automaticamente ao iniciar um trabalho** dispara um anúncio quando a telemetria sinaliza um novo trabalho; desmarque-a para apenas acompanhar os dados e fazer anúncios manuais.

Se o painel ficar em **AGUARDANDO ETS2 E PLUGIN SCS**, verifique se o jogo está aberto, se `scs-telemetry.dll` está na pasta correta e se o plugin foi carregado. A DLL é um componente separado instalado na pasta de plugins do jogo e não está embutida no executável do painel. O aplicativo só lê o bloco de memória do plugin; ele não injeta código no jogo nem altera seus arquivos.

## Formatação de cidades

`telemetria_ets2.py` expõe `limpar_cidade`, usada pelo motor nos nomes de origem e destino. Ela remove siglas das 27 UFs no final (por exemplo, `Sao_Paulo-SP`, `Santos (SP)` ou `Curitiba/PR`), normaliza underlines e hífens usados como separadores e corrige acentos de capitais e de cidades comuns nos mapas brasileiros. O dicionário inclui, entre outras, Juquiá, Pariquera-Açu, Cananéia, Apiaí, Capão Bonito, São Lourenço da Serra, Jacupiranga, Eldorado, Sete Barras e cidades do litoral sul paulista.

Nomes que não estejam no dicionário também têm UFs e separadores normalizados e são preservados; a lista de acentos é extensível conforme novos mapas adicionem cidades.

## Executar o painel

Na pasta do projeto:

```powershell
python app_rodoviaria.py
```

O painel salva preferências em `config_rodoviaria.json`. O anúncio usa `falar_rodoviaria.py`, que gera a locução com edge-tts, mistura o áudio com FFmpeg e reproduz o resultado. É necessária uma conexão com o serviço edge-tts. Mantenha `campainha.wav` e um áudio de fundo (`fundo_rodoviaria.wav` ou `fundo_rodoviaria.mp3`) ao lado dos scripts.

### Executar `RodoviariaETS2.exe`

Baixe o [RodoviariaETS2.exe para Windows](https://github.com/Messias8888437/sistema-voz-rodoviaria-ets2/releases/download/v1.0.0/RodoviariaETS2.exe) ou acesse a página da [release v1.0.0](https://github.com/Messias8888437/sistema-voz-rodoviaria-ets2/releases/tag/v1.0.0). Coloque o executável na mesma pasta que `falar_rodoviaria.py`, `telemetria_ets2.py`, `config_rodoviaria.json`, `campainha.wav` e `fundo_rodoviaria.wav` (ou `fundo_rodoviaria.mp3`). Abra o executável para iniciar o painel. Como o programa chama o motor Python como processo separado, Python 3.15+, `edge-tts` e `static-ffmpeg` precisam estar instalados e disponíveis no PATH. É necessária conexão com a internet para gerar a voz.

O suporte aos mapas é independente do SimHub e do mapa carregado: o motor normaliza os nomes de origem e destino recebidos do plugin, incluindo separadores, siglas de estados e acentos conhecidos. Também é possível informar a viagem manualmente. O perfil automático usa o nome da carga lido da telemetria (ou fornecido por `--cargo`): cargas de leite e laticínios selecionam **Leiteiro (Coleta de Leite)**; as demais selecionam **Passageiros (Rodoviária)**. Os modos também podem ser escolhidos manualmente no painel.

Exemplo de chamada direta do motor:

```powershell
python falar_rodoviaria.py --origem "São Paulo" --destino "Campinas" --hora "19 horas" --plataforma "4"
```

## Modos de anúncio

O painel oferece os perfis **Automático**, **Passageiros (Rodoviária)** e **Leiteiro (Coleta de Leite)**. Os modos passageiros e leiteiro geram anúncios e mixagens de áudio diferentes; os modos também podem ser selecionados diretamente no motor:

```powershell
python falar_rodoviaria.py --origem "São Paulo" --destino "Campinas" --hora "19 horas" --modo rodoviaria
python falar_rodoviaria.py --origem "Fazenda A" --destino "Laticínio B" --hora "19 horas" --modo leiteiro
```

Com a conexão ativa ao plugin, o perfil automático classifica a carga lida do ETS2: termos como `leite`, `milk`, `laticin`, `queijo`, `iogurte` ou `tanque` selecionam o modo leiteiro; as demais cargas selecionam o modo rodoviária. Na chamada direta do motor, informe `--cargo` para usar essa mesma detecção. O painel também permite forçar qualquer modo.

## Compilar o painel

```powershell
python -m PyInstaller --clean --noconfirm --noconsole --onefile --distpath "$env:TEMP\py_dist" --workpath "$env:TEMP\py_build" --specpath "$env:TEMP" --name "RodoviariaETS2" app_rodoviaria.py
Copy-Item "$env:TEMP\py_dist\RodoviariaETS2.exe" ".\RodoviariaETS2.exe" -Force
```

O executável é copiado para a raiz como `RodoviariaETS2.exe`. Feche instâncias abertas antes de substituí-lo. Para usar o painel compilado, mantenha `falar_rodoviaria.py`, `telemetria_ets2.py`, `config_rodoviaria.json`, `campainha.wav` e um áudio de fundo junto ao executável. Python e as dependências `edge-tts` e `static-ffmpeg` também precisam estar instalados e disponíveis no PATH, pois o painel inicia o motor como um script separado.

## Arquivos principais

- `app_rodoviaria.py`: painel gráfico.
- `falar_rodoviaria.py`: geração, mixagem e reprodução dos anúncios.
- `telemetria_ets2.py`: leitura do mapa de memória compartilhada do plugin SCS, formatação de cidades e classificação da carga.
- `gerar_audios.py`: geração dos arquivos WAV de campainha e áudio de fundo.
- `campainha.wav` e `fundo_rodoviaria.wav`: efeitos sonoros usados na mixagem.
