# Sistema de Voz Rodoviária para ETS2

Aplicativo em português para anúncios no **Euro Truck Simulator 2 1.62**, sem depender de um mapa específico ou do SimHub. A normalização de cidades foi preparada para nomes dos mapas brasileiros **Mapa Eldorado, Mapa EAA, Rotas Brasil e RBR**, além de outros mapas. O painel oferece os modos **Passageiros (Rodoviária)** e **Leiteiro (Coleta de Leite)**, além de controles de voz e volume.

## Requisitos

- Windows e Python **3.15 ou superior**, com `tkinter`.
- Pacotes Python `edge-tts` e `static-ffmpeg`.
- PyInstaller para compilar o executável.
- O plugin de telemetria `scs-telemetry.dll`, distribuído separadamente, caso queira instalá-lo para uso com ferramentas compatíveis.

Instale as dependências:

```powershell
py -3.15 -m pip install edge-tts static-ffmpeg pyinstaller
```

## Instalar o plugin de telemetria

1. Feche o ETS2.
2. Na pasta de instalação do jogo, crie `bin\win_x64\plugins` se ela ainda não existir. Por exemplo, em uma instalação Steam padrão:
   `C:\Program Files (x86)\Steam\steamapps\common\Euro Truck Simulator 2\bin\win_x64\plugins`
3. Obtenha `scs-telemetry.dll` da distribuição confiável do plugin e copie o arquivo para essa pasta.
4. Inicie o jogo novamente. Consulte a documentação do fornecedor do plugin para opções adicionais de instalação e funcionamento.

O sistema não depende do SimHub. Para instalar o plugin de telemetria, coloque `scs-telemetry.dll` em `Euro Truck Simulator 2\bin\win_x64\plugins` (consulte acima o exemplo do caminho completo da instalação Steam).

**Estado da leitura automática do jogo:** embora o painel ofereça os modos Passageiros e Leiteiro e o motor possa classificar automaticamente uma carga recebida em `--cargo`, esta versão ainda não consome a telemetria do `scs-telemetry.dll`. Portanto, não lê automaticamente a origem, o destino ou o horário atual do ETS2. Preencha esses dados no painel ou forneça-os ao motor pela linha de comando. Instalar a DLL, por si só, não conecta o plugin ao aplicativo.

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

Baixe `RodoviariaETS2.exe` na seção **Releases** do GitHub e coloque-o na mesma pasta que `falar_rodoviaria.py`, `telemetria_ets2.py`, `config_rodoviaria.json`, `campainha.wav` e `fundo_rodoviaria.wav` (ou `fundo_rodoviaria.mp3`). Abra o executável para iniciar o painel. Como o programa chama o motor Python como processo separado, Python 3.15+, `edge-tts` e `static-ffmpeg` precisam estar instalados e disponíveis no PATH. É necessária conexão com a internet para gerar a voz.

O suporte aos mapas é independente do SimHub e do mapa carregado: o motor normaliza os nomes de origem e destino informados, incluindo separadores, siglas de estados e acentos conhecidos. No painel, informe origem, destino, horário e plataforma; não há leitura automática desses dados do jogo nesta versão. Também é possível escolher um modo no painel ou usar o perfil automático quando a carga é fornecida ao motor por `--cargo`.

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

No perfil automático, o motor classifica o texto passado em `--cargo`: termos como `leite`, `milk`, `laticin`, `queijo`, `iogurte` ou `tanque` selecionam o modo leiteiro; outros valores selecionam o modo rodoviária. Para uma chamada automática, forneça também `--cargo`. Essa seleção de modo funciona sem SimHub, mas não lê a carga nem os dados da viagem do jogo nesta versão.

## Compilar o painel

```powershell
python -m PyInstaller --noconfirm --noconsole --onefile --distpath "$env:TEMP\py_dist" --workpath "$env:TEMP\py_build" --specpath "$env:TEMP" --name "RodoviariaETS2" app_rodoviaria.py
Copy-Item "$env:TEMP\py_dist\RodoviariaETS2.exe" ".\RodoviariaETS2.exe" -Force
```

O executável é copiado para a raiz como `RodoviariaETS2.exe`. Feche instâncias abertas antes de substituí-lo. Para usar o painel compilado, mantenha `falar_rodoviaria.py`, `telemetria_ets2.py`, `config_rodoviaria.json`, `campainha.wav` e um áudio de fundo junto ao executável. Python e as dependências `edge-tts` e `static-ffmpeg` também precisam estar instalados e disponíveis no PATH, pois o painel inicia o motor como um script separado.

## Arquivos principais

- `app_rodoviaria.py`: painel gráfico.
- `falar_rodoviaria.py`: geração, mixagem e reprodução dos anúncios.
- `telemetria_ets2.py`: formatação de cidades e classificação do texto da carga; não lê dados do jogo.
- `gerar_audios.py`: geração dos arquivos WAV de campainha e áudio de fundo.
- `campainha.wav` e `fundo_rodoviaria.wav`: efeitos sonoros usados na mixagem.
