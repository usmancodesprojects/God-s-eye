// Optional one-command launcher after following README setup. No extra npm dependencies.
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('../',import.meta.url));
const win=process.platform==='win32';
const venv=path.join(root,'backend','.venv',win?'Scripts/python.exe':'bin/python');
const python=process.env.PYTHON_EXECUTABLE || (existsSync(venv)?venv:win?'python':'python3');
const envFile=path.join(root,'backend','.env');
const children=[];
let stopping=false;
function stop(code=0) {
  if(stopping)return;stopping=true;
  for(const child of children) {
    if(!child.pid)continue;
    try {
      if(win)spawn('taskkill',['/pid',String(child.pid),'/T','/F']);
      else process.kill(-child.pid,'SIGTERM');
    }catch{}
  }
  process.exitCode=code;
}
function start(command,args,cwd) {
  const child=spawn(command,args,{cwd,stdio:'inherit',env:process.env,detached:!win});
  children.push(child);
  child.on('error',e=>{console.error(e.message);stop(1);});
  child.on('exit',code=>{if(!stopping)stop(code??1);});
}
start(python,['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000',...(existsSync(envFile)?['--env-file',envFile]:[])],path.join(root,'backend'));
// On Windows cmd.exe resolves npm.cmd without shell-quoting user-controlled text.
if(win)start(process.env.ComSpec||'cmd.exe',['/d','/s','/c','npm run dev'],path.join(root,'frontend'));
else start('npm',['run','dev'],path.join(root,'frontend'));
process.on('SIGINT',()=>stop());process.on('SIGTERM',()=>stop());
