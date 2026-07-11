const payload = JSON.parse(process.argv[2] || '{}');

async function sendSlack({ recipient, message }) {
  const webhook = process.env.SLACK_WEBHOOK_URL;
  if (!webhook) {
    throw new Error('Slack is not configured. Set SLACK_WEBHOOK_URL before sending Slack messages.');
  }

  const body = { text: recipient ? `To ${recipient}: ${message}` : message };
  const response = await fetch(webhook, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`Slack returned ${response.status}: ${await response.text()}`);
  }

  return `Slack message sent${recipient ? ` to ${recipient}` : ''}.`;
}

async function main() {
  const platform = String(payload.platform || '').toLowerCase();
  if (platform === 'slack') {
    console.log(await sendSlack(payload));
    return;
  }
  throw new Error(`Node bridge does not support ${platform || 'this platform'} yet.`);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
