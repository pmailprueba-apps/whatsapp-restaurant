import makeWASocket, { useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import { Boom } from '@hapi/boom';
import express from 'express';
import qrcode from 'qrcode';
import qrcodeTerminal from 'qrcode-terminal';

const PORT = process.env.WEBJS_PORT || 3001;
const PYTHON_WEBHOOK = process.env.PYTHON_WEBHOOK_URL || 'http://localhost:8000/webhook/whatsapp';
const PHONE_NUMBER = process.env.BOT_PHONE_NUMBER || '5214446506790';

const app = express();
app.use(express.json());

let pairingCode = null;
let isReady = false;
let sock = null;

async function startBot() {
  const { state, saveCreds } = await useMultiFileAuthState('./session-data');

  sock = makeWASocket({
    auth: state,
    printQRInTerminal: false,
    browser: ['Chrome', 'Mac', '25.0.0'],
    syncFullHistory: false,
  });

  if (!state.creds.registered) {
    try {
      const code = await sock.requestPairingCode(PHONE_NUMBER);
      pairingCode = code;
      const display = code.match(/.{1,4}/g).join('-');
      console.log('\n═══════════════════════════════════════');
      console.log('  CÓDIGO:', display);
      console.log('═══════════════════════════════════════');
      console.log('1. WhatsApp → Dispositivos vinculados');
      console.log('2. "Vincular con número de teléfono"');
      console.log('3. Ingresa:', display);
    } catch (e) {
      console.log('[WhatsApp Bot] Error pairing code, usando QR');
      sock.ev.on('connection.update', ({ qr }) => {
        if (qr) {
          pairingCode = null;
          qrcodeTerminal.generate(qr, { small: true });
          console.log('\n[WhatsApp Bot] Escanea QR: https://cabbie-hammock-railway.ngrok-free.dev\n');
        }
      });
    }
  }

  sock.ev.on('connection.update', ({ connection, lastDisconnect }) => {
    if (connection === 'open') {
      isReady = true;
      pairingCode = null;
      console.log('[WhatsApp Bot] Conectado!');
    }
    if (connection === 'close') {
      isReady = false;
      const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
      if (shouldReconnect) setTimeout(startBot, 1000);
    }
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify') return;

    for (const msg of messages) {
      if (!msg.message || msg.key.fromMe) continue;

      const rawJid = msg.key.remoteJid || '';
      const phone = rawJid.replace(/@[^@]+$/, '').replace(/[^0-9]/g, '');
      const text = msg.message.conversation || msg.message.extendedTextMessage?.text || '';

      if (!text || !phone || phone.length < 10) continue;

      console.log(`[WhatsApp Bot] ${phone}: ${text}`);

      for (let i = 0; i < 3; i++) {
        try {
          const r = await fetch(PYTHON_WEBHOOK, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone, text, profile_name: '', msg_type: 'text' }),
          });
          if (r.ok) break;
        } catch (e) {
          if (i === 2) console.error(`[WhatsApp Bot] Error: ${e.message}`);
          await new Promise(r => setTimeout(r, 1000));
        }
      }
    }
  });
}

startBot();

app.get('/', (req, res) => {
  res.send(`<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>WhatsApp Bot</title>
<style>
body{font-family:-apple-system,sans-serif;text-align:center;padding:20px;background:#1a1a1a;color:white;margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{max-width:420px;width:100%;padding:30px 20px;text-align:center}
.code{font-size:40px;font-weight:bold;letter-spacing:5px;background:#25D366;color:#1a1a1a;padding:20px;border-radius:12px;margin:20px 0;font-family:monospace}
.status{font-size:20px;margin:20px 0}
.connected{color:#25D366;font-weight:bold}
.waiting{color:#999}
.instructions{color:#aaa;font-size:15px;line-height:1.7;margin-top:25px;text-align:left}
</style>
</head>
<body>
<div class="card">
  <h1 style="margin:0 0 10px">🤖 WhatsApp Bot</h1>
  <div id="c"><div class="status waiting">⏳ Iniciando...</div></div>
  <div class="instructions" id="i" style="display:none">
    <strong>Instrucciones:</strong><br>
    1️⃣ WhatsApp → Dispositivos vinculados<br>
    2️⃣ "Vincular con número de teléfono"<br>
    3️⃣ Ingresa el código de arriba
  </div>
</div>
<script>
async function check() {
  const r = await fetch('/status'); const d = await r.json();
  const c = document.getElementById('c'); const i = document.getElementById('i');
  if(d.ready) { c.innerHTML = '<div class="status connected">✅ Conectado!</div>'; i.style.display='none'; }
  else if(d.code) {
    c.innerHTML = '<div class="code">'+d.code.replace(/(.{4})/g,'$1-').slice(0,-1)+'</div><div class="status">🔗 Ingresa el código</div>';
    i.style.display='block';
  } else { c.innerHTML = '<div class="status waiting">⏳ Conectando...</div>'; }
}
check(); setInterval(check, 2000);
</script>
</body>
</html>`);
});

app.get('/status', (req, res) => {
  res.json({ ready: isReady, code: pairingCode });
});

app.post('/send-text', async (req, res) => {
  const { to, text } = req.body;
  if (!to || !text) return res.status(400).json({ error: 'required' });
  try {
    const jid = to.includes('@') ? to : `${to}@s.whatsapp.net`;
    await sock.sendMessage(jid, { text });
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`[WhatsApp Bot] Puerto ${PORT}`);
  console.log(`[WhatsApp Bot] Webhook: ${PYTHON_WEBHOOK}`);
});
