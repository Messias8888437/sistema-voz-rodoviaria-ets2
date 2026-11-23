# Sistema de Voz Rodoviária para ETS2

Aplicativo em português para anúncios no **Euro Truck Simulator 2 1.62 com o Mapa EAA**. O painel permite escolher o perfil de anúncio, ajustar a voz e os volumes e preencher manualmente os dados da viagem.

## Requisitos

- Windows e Python **3.15 ou superior**, com `tkinter`.
- Pacotes Python `edge-tts` e `static-ffmpeg`.
- PyInstaller para compilar o executável.
- O plugin de telemetria `scs-telemetry.dll` para obter dados do jogo. O plugin é distribuído separadamente.

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

**Limitação desta versão:** instalar a DLL, por si só, não conecta a telemetria ao aplicativo. O código deste repositório ainda não lê origem, destino, horário ou carga do jogo nem recebe notificações de início de trabalho. O painel solicita origem, destino e horário manualmente; o motor de anúncios aceita esses valores por argumentos de linha de comando.

## Executar o painel

Na pasta do projeto:

```powershell
python app_rodoviaria.py
```

O painel salva preferências em `config_rodoviaria.json`. O anúncio usa `falar_rodoviaria.py`, que gera a locução com edge-tts, mistura o áudio com FFmpeg e reproduz o resultado. É necessária uma conexão com o serviço edge-tts. Mantenha `campainha.wav` e um áudio de fundo (`fundo_rodoviaria.wav` ou `fundo_rodoviaria.mp3`) ao lado dos scripts.

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

No perfil automático, o motor classifica o texto passado em `--cargo`: termos como `leite`, `milk`, `laticin`, `queijo`, `iogurte` ou `tanque` selecionam o modo leiteiro; outros valores selecionam o modo rodoviária. Para uma chamada automática, forneça também `--cargo`. Esta classificação não lê o jogo por conta própria.

## Compilar o painel

```powershell
py -3.15 -m PyInstaller --noconfirm --onefile --windowed --name RodoviariaETS2 app_rodoviaria.py
```

O executável é criado em `dist\RodoviariaETS2.exe`. Para usar o painel compilado, mantenha `falar_rodoviaria.py`, `telemetria_ets2.py`, `config_rodoviaria.json`, `campainha.wav` e um áudio de fundo junto ao executável. Python e as dependências `edge-tts` e `static-ffmpeg` também precisam estar instalados e disponíveis no PATH, pois o painel inicia o motor como um script separado.

## Arquivos principais

- `app_rodoviaria.py`: painel gráfico.
- `falar_rodoviaria.py`: geração, mixagem e reprodução dos anúncios.
- `telemetria_ets2.py`: classificação de carga para escolher o perfil automático; não lê dados do jogo.
- `gerar_audios.py`: geração dos arquivos WAV de campainha e áudio de fundo.
- `campainha.wav` e `fundo_rodoviaria.wav`: efeitos sonoros usados na mixagem.
