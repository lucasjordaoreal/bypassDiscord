# DiscordCrack v1.0 - BR Bypass + Quality Unlock

Contra a censura do governo brasileiro (ANPD/2026).  
Libera **camera**, **Go Live** e **transmissao de tela** em qualidade maxima sem Nitro.

---

## Requisitos

- **Windows 10/11** (64-bit)
- **Python 3.10+** — [python.org/downloads](https://python.org/downloads)
- **Tor Browser** — [Tor Browser](https://download.torproject.org/) Opcional, porém recomendado!

---

## Instalacao rapida 

```
pip install -r requirements.txt
python main.py
```

> *Recomendado: venv*
>
> ```
> python -m venv venv
> venv\Scripts\Activate.ps1
> pip install -r requirements.txt
> python main.py
> ```

---

## Como usar (passo a passo)

### Passo 1 — Patch de ASAR

1. Execute `python main.py` (o app pede admin automaticamente via UAC)
2. Va para a aba **Patcher ASAR**
3. Confira o campo **Caminho do Discord**:
   - Correto:   `C:\Users\User\AppData\Local\Discord`
   - O campo deve apontar para a pasta **Discord**, nao para a subpasta `app-*`
   - Clique **Detectar** para confirmar
4. Deixe ambas as opcoes marcadas e clique **APLICAR PATCHES**
5. Aguarde `PATCHES APLICADOS COM SUCESSO!`

### Passo 2 — Proxy Launcher

O patch de ASAR remove bloqueios no **cliente** (UI, botoes, qualidade).
O Discord tambem verifica seu IP no **servidor** - use o proxy so para o Discord.
Isso **nao e uma VPN de sistema** - jogos continuam na sua conexao normal.

#### Opcao A — Tor Browser (recomendado)

1. Baixe: [torproject.org](https://www.torproject.org)
2. Abra o Tor Browser e aguarde conectar (nao feche)
3. No app, selecione **Tor Browser (127.0.0.1:9150)**
4. Clique **Lancar Discord COM Proxy**

#### Opcao B — Proxy gratuito automatico

1. Selecione **Auto**
2. Clique **Buscar** para buscar e testar proxies SOCKS5
3. Aguarde a lista com latencias aparecer
4. Clique **Lancar Discord COM Proxy**

#### Opcao C — Proxy proprio

1. Selecione **Personalizado**
2. Preencha Host e Porta do seu proxy SOCKS5
3. Clique **Testar** -> **Lancar Discord COM Proxy**

---

## Solucao de problemas

### ASAR nao encontrado

O campo **Caminho do Discord** deve apontar para:
```
C:\Users\SEU_USUARIO\AppData\Local\Discord
```
**Nao** para `Discord\app-1.0.9258` (sem a subpasta).

Para achar o caminho correto:
1. Abra o Explorer
2. Cole na barra de endereco: `%LOCALAPPDATA%\Discord`
3. Copie o caminho exibido e cole no campo do app

O app busca o ASAR em:
```
Discord\app-*\modules\discord_desktop_core-*\discord_desktop_core\core.asar
Discord\resources\app.asar
```

### Erro de permissao ao aplicar patches

Execute como **Administrador**:
- Clique com botao direito em `main.py` -> Abrir com Python -> Executar como Administrador
- Ou: `Start-Process python main.py -Verb RunAs`

### Discord nao inicia apos o patch

1. Abra o DiscordCrack
2. Aba **Patcher ASAR** -> clique **Restaurar Original**

Ou manualmente no Explorer:
```
Renomear: core.asar.original_backup  ->  core.asar
```

### Video ainda bloqueado mesmo com proxy

- Use o **Tor Browser** (mais confiavel)
- Proxies gratuitos podem cair - clique **Buscar** novamente
- Garanta que o Discord foi aberto PELO botao do app (nao manualmente)

---

## Como funciona

```
[PATCH DE ASAR - lado do cliente]
  Desempacota core.asar em Python puro (sem Node.js)
  Aplica regex nos arquivos .js:
    canUseHighVideoFPS(){return true}       <- sem check de Nitro
    isGoLiveRegionBlocked(){return false}   <- sem check de regiao
    'brazil':false                          <- feature flag desativada
    fps: 120, maxResolution: 2160           <- qualidade maxima
  Reempacota e substitui core.asar (backup automatico)

[PROXY POR-PROCESSO - lado do servidor]
  Discord.exe iniciado com flag nativa do Electron:
    --proxy-server=socks5://host:porta
  So o Discord usa o proxy
  Jogos e outros apps usam sua conexao direta normalmente
```

---

## Restaurar o Discord original

No app: **Patcher ASAR** -> **Restaurar Original**

Manualmente:
```
Renomear core.asar.original_backup para core.asar
```

---

> **Aviso:** Use por sua propria conta e risco.
> A informacao e o acesso a comunicacao devem ser livres.
> **Contra a censura. Setembro 2026.**
