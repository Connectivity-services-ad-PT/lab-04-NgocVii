const { spawnSync } = require('child_process');

function findPython() {
  const candidates = ['python', 'python3', 'py'];
  for (const cmd of candidates) {
    const result = spawnSync(cmd, ['--version'], { shell: true, stdio: 'ignore' });
    if (result.status === 0) {
      return cmd;
    }
  }
  return null;
}

function findDocker() {
  const result = spawnSync('docker', ['--version'], { shell: true, stdio: 'ignore' });
  return result.status === 0;
}

const pythonCmd = findPython();
if (!pythonCmd) {
  console.error('ERROR: Python 3 is not installed or not available on PATH.');
  console.error('Please install Python 3 and try again, or run the service with Docker:');
  console.error('  npm run docker:build');
  console.error('  npm run docker:run');
  if (findDocker()) {
    console.error('Docker is available on this machine, so you can also use the Docker commands.');
  }
  process.exit(1);
}

const uvicorn = spawnSync(pythonCmd, ['-m', 'uvicorn', 'iot_app.main:app', '--app-dir', 'src', '--host', '0.0.0.0', '--port', '8000'], { stdio: 'inherit', shell: true });
process.exit(uvicorn.status || 1);
