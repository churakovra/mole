// Development-only real-browser harness. The installed skill needs no Node.
const fs = require("node:fs");
const path = require("node:path");
const {spawn} = require("node:child_process");
const {pathToFileURL} = require("node:url");
const [browser, directory, file, width, screenshot] = process.argv.slice(2);
const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
const chrome = spawn(browser, ["--headless", "--no-first-run", "--disable-background-networking",
  "--disable-component-update", "--disable-sync", "--disable-default-apps", "--disable-extensions",
  "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1",
  "--remote-debugging-port=0", "--remote-debugging-address=127.0.0.1", "--user-data-dir=" + path.join(directory, "profile"), "about:blank"], {stdio:"ignore"});
let socket;
async function run() {
  const portFile = path.join(directory, "profile", "DevToolsActivePort");
  for(let i=0;i<200 && !fs.existsSync(portFile);i++) {
    if (chrome.exitCode !== null) throw new Error("Chrome exited " + chrome.exitCode);
    await pause(50);
  }
  const port = fs.readFileSync(portFile,"utf8").split("\n")[0];
  const targets = await (await fetch("http://127.0.0.1:" + port + "/json/list")).json();
  const target = targets.find(t=>t.type==="page");
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve,reject)=> {socket.onopen=resolve;socket.onerror=reject;});
  let sequence=0;
  const pending = new Map();
  socket.onmessage = event => {
    const response=JSON.parse(event.data);
    if(pending.has(response.id)) {
      const [resolve,reject]=pending.get(response.id); pending.delete(response.id);
      if(response.error) reject(new Error(JSON.stringify(response.error))); else resolve(response.result);
    }
  };
  const call = (method,params={}) => new Promise((resolve,reject)=>{
    const id=++sequence;pending.set(id,[resolve,reject]);socket.send(JSON.stringify({id,method,params}));
  });
  await call("Page.enable");
  await call("Emulation.setDeviceMetricsOverride", {width:Number(width),height:844,deviceScaleFactor:1,mobile:false});
  await call("Page.navigate", {url:pathToFileURL(file).href});
  let html="";
  for(let i=0;i<100;i++) {
    const result=await call("Runtime.evaluate",{expression:"document.documentElement.outerHTML",returnByValue:true});
    html=result.result.value || "";
    if(html.includes('<pre id="test-results">')) break;
    await pause(50);
  }
  if(screenshot) {
    const result=await call("Page.captureScreenshot",{format:"png",captureBeyondViewport:false});
    fs.writeFileSync(screenshot,Buffer.from(result.data,"base64"));
  }
  process.stdout.write(html);
}
run().catch(error=>{process.stderr.write(String(error));process.exitCode=1;}).finally(()=>{
  if(socket) socket.close();chrome.kill();
});
