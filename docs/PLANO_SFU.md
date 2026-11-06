# Call híbrida: P2P + SFU (LiveKit) num servidor gratuito da Oracle

> **Estado (Rodada 39, 06/11/2026): PREPARADO, NÃO LIGADO.** O servidor já sabe escolher o transporte de cada call, emitir o token de entrada no SFU e avisar a call quando
> ela muda. O que **falta** é o adaptador do navegador (a parte que de fato conecta no SFU) e o SFU em si: nenhum dos dois pôde ser testado aqui, porque o servidor da
> Oracle ainda não existe. **Enquanto o adaptador não existir, ligar as variáveis não muda nada: toda call continua P2P.** Nada abaixo foi testado contra um LiveKit de verdade.

## Por que um SFU

Hoje a call é uma **malha P2P** (PeerJS): cada pessoa manda a própria câmera/tela pra **cada** outra. Com N pessoas, o upload de quem transmite é `N-1` vezes o vídeo. Passou de
4-5 pessoas, ou quando alguém compartilha tela em 1080p, a conexão de quem manda engasga e a call inteira sofre. Num **SFU** cada um manda UMA cópia pro servidor, e o servidor
repassa a quem assiste (e escolhe a qualidade certa pra cada espectador). O custo muda de lugar: sai da internet de quem transmite e vai pra banda do servidor.

**Híbrido** = o melhor dos dois: call pequena e ligação de DM seguem P2P (mais barato, mais privado, latência mínima, não gasta o servidor), e a call grande migra pro SFU.

## O que já está no código

| Peça | Onde | O que faz |
|---|---|---|
| Política e token | `app/sfu.py` | `CALL_MODE` (`p2p` padrão, `sfu`, `auto`), `CALL_P2P_MAX` (padrão 4), validação de `LIVEKIT_URL` (só `wss://`), `politica(n, dm)`, escolha **fixa por call** (nasce P2P, passou do limite vira SFU e fica até esvaziar), e `emitir_token()`: JWT HS256 no formato do LiveKit, feito à mão (`hmac`), sem dependência nova |
| Eventos | `app/sfu_events.py` | `sfu_pedir_token` → `sfu_token` (só quem está **de verdade** na call; sala derivada da call, nunca do cliente; ouvinte do palco recebe token que **não publica**; em canal de stream só o apresentador recebe `screen_share`; freio de 2 s) e `call_transporte` (avisa a sala UMA vez quando a call passa pro SFU) |
| Ganchos | `app/events.py` | `entrar_call` chama `ao_entrar_na_call`, `_tirar_da_call` chama `ao_sair_da_call` (call vazia esquece o transporte) |
| Página | `chat.html` | `CALL_POLITICA` = `{modo, limite_p2p, sfu, url}`. **Nunca** a chave nem o segredo |
| Cliente | `static/js/call_transporte.js` | guarda a política, escuta `call_transporte`, pede o token e define o **contrato do adaptador**. Sem adaptador, `transporteDaCall()` responde sempre `'p2p'` |
| Testes | `testes/fumaca_sfu.py`, `testes/call_transporte_logica.js` | configuração, política, token verificado por um HMAC independente, eventos, página sem segredo, módulo do cliente no Node |

## Passo a passo: o servidor da Oracle

Valores da Oracle e do LiveKit mudam: **confira a documentação atual de cada um** antes de seguir (marquei com "conferir" o que mais costuma mudar).

1. **Conta**: Oracle Cloud, plano *Always Free* (pede cartão só pra verificar). Escolha a região de casa com cuidado (não muda depois): São Paulo (`sa-saopaulo-1`) ou Vinhedo (`sa-vinhedo-1`), a mais perto de quem usa.
2. **Máquina**: instância **Ampere A1 (ARM)**, Ubuntu 22.04 ou 24.04. O Always Free costuma dar até 4 OCPU e 24 GB somando as instâncias A1 (conferir). Muitas vezes a região diz "sem capacidade": tente de novo em outro horário, ou em outro domínio de disponibilidade.
   A Oracle pode **recolher instância Always Free ociosa** (conferir a regra de "reclamation"); passar a conta pra *Pay As You Go* mantendo só os recursos gratuitos costuma evitar isso e não cobra enquanto ficar nos limites.
3. **IP público fixo** (um IP reservado é gratuito) e um **domínio ou subdomínio** apontando pra ele (`sfu.seudominio.com`). O Pantheon é `https`, então o SFU **precisa** de `wss://` com certificado de verdade: IP puro não serve.
4. **Portas** (precisam abrir em DOIS lugares: na *Security List/NSG* da rede da Oracle **e** no firewall da própria máquina, porque a imagem Ubuntu da Oracle vem com `iptables` fechado):
   - `80/tcp` e `443/tcp` (certificado e sinalização `wss://` pelo proxy)
   - `7881/tcp` (WebRTC por TCP, quando o UDP é bloqueado)
   - `3478/udp` e `5349/tcp` (TURN próprio do LiveKit) ou só o `443` se usar TURN/TLS
   - `50000-60000/udp` (a mídia; dá pra reduzir a faixa na configuração do LiveKit com `rtc.port_range_start/end`, ou usar uma porta UDP só)
   Salve as regras do `iptables` (`netfilter-persistent save`) senão elas somem no reinício.
5. **LiveKit**: o jeito mais curto é o gerador oficial (`docker run --rm -it -v$PWD:/output livekit/generate`), que escreve um `docker-compose` com o servidor, o Caddy (certificado automático) e o TURN. As imagens têm versão ARM64 (conferir). Rode `docker compose up -d`.
6. **Chaves**: `docker run --rm livekit/livekit-server generate-keys` cria o par `API key / secret`. O segredo precisa ter **32+ caracteres** (o código recusa menos que isso). Coloque o mesmo par no `livekit.yaml` (`keys:`).
7. **Render** (Environment do serviço do Pantheon), depois **redeploy**:
   ```
   LIVEKIT_URL=wss://sfu.seudominio.com
   LIVEKIT_API_KEY=<a chave>
   LIVEKIT_API_SECRET=<o segredo>
   CALL_P2P_MAX=4
   CALL_MODE=auto        # só depois do adaptador estar pronto; antes disso pode deixar p2p
   ```
   **Kill switch**: `CALL_MODE=p2p` e redeploy. Sem chave, URL inválida ou segredo curto o código volta sozinho pra P2P (nunca derruba a call por falta de configuração).

## O que ainda precisa ser feito (o adaptador do navegador)

1. **Baixar a `livekit-client`** (Apache 2.0) e hospedar em `app/static/js/vendor/` (como o `lottie_light.min.js`: sem CDN, sem rastreio de terceiros).
2. **Escrever o adaptador** que cumpre o contrato do `call_transporte.js` (`conectar`, `publicar`, `parar`, `desconectar`) com `Room.connect(url, token)`, `publishTrack`, e os eventos de faixa remota.
3. **Ligar no `chat.html`**: ao entrar na call, `CallTransporte.transporteDaCall(canal)`; se for `'sfu'`, `pedirToken` + `conectar`; se for `'p2p'`, o fluxo de hoje.
4. **Migrar uma call que já está rolando**: ao receber `call_transporte = sfu`, cada cliente pede o token, conecta, publica as faixas que já tem (microfone, câmera, tela) e só então fecha as ligações PeerJS. Quem não migrar em alguns segundos continua P2P (a call não pode cair no meio).
5. **Trocar o que hoje depende do PeerJS**: cartões por `peer_id` viram cartões por identidade (`u<id>`, que o servidor já conhece em `participantes_call`); o detector de quem fala (`monitorarVolume`) pode usar `ActiveSpeakersChanged`; a qualidade da tela (hoje ajustada na mão por `RTCRtpSender`) passa a ser *simulcast* + *dynacast* do próprio LiveKit; o **compositor de gravação/clipes** continua lendo `<video>`, então basta anexar a faixa remota num elemento.
6. **Stream/palco**: o token já separa quem pode publicar tela (só o apresentador) e quem só ouve; quando a vez de transmitir mudar, o cliente pede **outro token** (o permissão vem no token, não muda no meio).
7. **Testar de verdade**: primeiro um LiveKit local (`livekit-server --dev` usa `devkey/secret`, e esse segredo curto é recusado pelo nosso código: use um par gerado), depois o da Oracle com 2, 5 e 10 pessoas e com tela compartilhada.

## Banda (a conta que decide se cabe no plano grátis)

Estimativa de ordem de grandeza: uma tela a 2,5 Mbps vista por 9 pessoas = ~22,5 Mbps de saída ≈ **10 GB por hora** de transmissão. Se o plano dá ~10 TB/mês de saída (conferir), isso são ~1000 horas assim por mês: sobra bastante pra uma comunidade pequena, mas **meça** (o painel do LiveKit e o da Oracle mostram o consumo). O limite real costuma ser a banda, não a CPU.

## Segurança e privacidade

- **O segredo só existe no Render e no LiveKit.** O token tem 10 minutos de validade (só vale pra *entrar*), leva só `u<id>` e o nome, e a sala sai da call que o servidor conferiu.
- Não exponha a API administrativa do LiveKit nem o Redis pra internet; só as portas da lista acima.
- Com o SFU, a mídia **passa pelo seu servidor** (no P2P ela nunca passa). Isso muda o que é verdade sobre a privacidade da call. Os Termos de hoje (`templates/termos.html`) só dizem que chamadas "poderão ser analisadas quando esse recurso estiver ativo"; antes de ligar o SFU, escreva ali, em linguagem simples, que a mídia das calls grandes passa pelo servidor de mídia do Pantheon (e que não é gravada, se for o caso) e suba a `VERSAO` em `termos.py` pra todo mundo aceitar de novo.
- Em compensação, só com o SFU dá pra **moderar a call de verdade** (o Guardião hoje não consegue ver chamada porque ela é P2P): o LiveKit tem *Egress* (gravar/capturar quadros) e *Agents*. É um projeto à parte, com decisão do dono sobre o que analisar e por quanto tempo guardar.
- Backup: se o SFU cair, `CALL_MODE=p2p` devolve tudo ao normal; o estado do transporte mora em memória e zera a cada reinício do servidor (as calls também).

## Checklist do dono

- [ ] Conta Oracle + instância A1 + IP reservado + domínio
- [ ] Portas abertas na rede **e** no firewall da máquina (e salvas)
- [ ] LiveKit no ar (gerador oficial) e `wss://` com certificado válido
- [ ] Par de chaves gerado; segredo com 32+ caracteres
- [ ] Variáveis no Render e redeploy (`CALL_MODE` só `auto` quando o adaptador existir)
- [ ] Adaptador do navegador (passos acima) e teste com 2, 5 e 10 pessoas
- [ ] Termos atualizados e `VERSAO` subida (a mídia das calls grandes passa pelo servidor)
