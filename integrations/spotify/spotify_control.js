const { execFile } = require('child_process');

const payload = JSON.parse(process.argv[2] || '{}');

function run(command, args) {
  return new Promise((resolve, reject) => {
    execFile(command, args, { windowsHide: true }, (error, stdout, stderr) => {
      if (error) {
        reject(new Error((stderr || error.message || '').trim()));
        return;
      }
      resolve((stdout || '').trim());
    });
  });
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function openTarget(target) {
  if (process.platform === 'win32') {
    await run('cmd.exe', ['/c', 'start', '', target]);
    return;
  }

  if (process.platform === 'darwin') {
    await run('open', [target]);
    return;
  }

  await run('xdg-open', [target]);
}

async function sendMediaKey(name) {
  const keyCodes = {
    playpause: 0xB3,
    next: 0xB0,
    previous: 0xB1,
  };

  const keyCode = keyCodes[name];
  if (!keyCode) {
    throw new Error(`Unsupported Spotify media key: ${name}`);
  }

  if (process.platform !== 'win32') {
    throw new Error('Spotify media key automation is currently implemented for Windows.');
  }

  const script = `
    Add-Type -TypeDefinition @"
    using System;
    using System.Runtime.InteropServices;
    public class MediaKeys {
      [DllImport("user32.dll")]
      public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
    }
"@
    [MediaKeys]::keybd_event(${keyCode}, 0, 0, [UIntPtr]::Zero)
    [MediaKeys]::keybd_event(${keyCode}, 0, 2, [UIntPtr]::Zero)
  `;

  await run('powershell.exe', [
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-Command',
    script,
  ]);
}

async function sendEnter() {
  if (process.platform !== 'win32') return;
  await run('powershell.exe', [
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-Command',
    "$ws = New-Object -ComObject WScript.Shell; $ws.SendKeys('{ENTER}')",
  ]);
}

async function playSpotify(query) {
  if (!query) {
    await openTarget('spotify:');
    await delay(1000);
    await sendMediaKey('playpause');
    return 'Spotify playback toggled.';
  }

  await openTarget(`spotify:search:${encodeURIComponent(query)}`);
  await delay(3000);
  await sendEnter();
  return `Spotify search opened for ${query}.`;
}

async function main() {
  const action = String(payload.action || '').toLowerCase();
  const query = String(payload.query || '').trim();

  if (action === 'open') {
    await openTarget('spotify:');
    console.log('Opening Spotify.');
    return;
  }

  if (action === 'play') {
    console.log(await playSpotify(query));
    return;
  }

  if (action === 'playpause' || action === 'next' || action === 'previous') {
    await sendMediaKey(action);
    console.log(`Spotify ${action} command sent.`);
    return;
  }

  throw new Error(`Spotify bridge does not support ${action || 'that command'} yet.`);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
