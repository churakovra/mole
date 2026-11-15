// Development-only real-browser harness. The installed skill needs no Node.
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const {spawn} = require("node:child_process");
const {pathToFileURL} = require("node:url");
const [browser, directory, file, width, screenshot] = process.argv.slice(2);
const harnessDeadline = Date.now() + 18000;
const remainingMs = () => Math.max(0,harnessDeadline-Date.now());
const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
async function bounded(promise,milliseconds,label) {
  const limit = Math.min(milliseconds,remainingMs());
  if(limit<=0) throw new Error(`Browser harness timed out before ${label}.`);
  let timer;
  try {
    return await Promise.race([promise,new Promise((_,reject)=>{
      timer=setTimeout(()=>reject(new Error(`${label} timed out after ${limit} ms.`)),limit);
    })]);
  } finally { clearTimeout(timer); }
}

class StartupError extends Error {}

async function attempt() {
  const profile = fs.mkdtempSync(path.join(directory, "mole-chrome-"));
  const chrome = spawn(browser, ["--headless", "--no-first-run", "--disable-background-networking",
    "--disable-component-update", "--disable-sync", "--disable-default-apps", "--disable-extensions",
    "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1",
    "--remote-debugging-port=0", "--remote-debugging-address=127.0.0.1", "--remote-allow-origins=*",
    "--user-data-dir=" + profile,
    "about:blank"], {stdio:["ignore","ignore","pipe"]});
  let chromeError = "";
  let spawnError = null;
  chrome.on("error", error => { spawnError = error; });
  chrome.stderr.setEncoding("utf8");
  chrome.stderr.on("data", chunk => { chromeError = (chromeError + chunk).slice(-3000); });
  let socket;
  let closeBrowser;
  try {
    const portFile = path.join(profile, "DevToolsActivePort");
    const deadline = Date.now() + Math.min(4000,remainingMs());
    while (!fs.existsSync(portFile) && Date.now() < deadline) {
      if (spawnError) throw new StartupError(`Chrome could not start: ${spawnError.message}. ${chromeError}`);
      if (chrome.exitCode !== null || chrome.signalCode !== null) {
        throw new StartupError(`Chrome exited before DevTools started (code ${chrome.exitCode}, signal ${chrome.signalCode || "none"}). ${chromeError}`);
      }
      await pause(50);
    }
    if (!fs.existsSync(portFile)) throw new StartupError(`Timed out waiting for DevToolsActivePort after 4000 ms. ${chromeError}`);
    let portText;
    try { portText = fs.readFileSync(portFile, "utf8"); }
    catch (error) { throw new StartupError(`DevToolsActivePort is unreadable: ${error.message}. ${chromeError}`); }
    const port = Number(portText.split("\n")[0]);
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      throw new StartupError(`DevToolsActivePort contains an invalid port. ${chromeError}`);
    }
    const targets = await (await fetch("http://127.0.0.1:" + port + "/json/list",
      {signal:AbortSignal.timeout(remainingMs())})).json();
    const target = targets.find(item => item.type === "page");
    if (!target) throw new Error("Chrome started without a page target.");
    socket = new WebSocket(target.webSocketDebuggerUrl);
    await bounded(new Promise((resolve,reject) => {
      socket.onopen=resolve;
      socket.onerror=event=>reject(new StartupError(`DevTools websocket failed to open: ${event.message || "connection error"}`));
      socket.onclose=()=>reject(new StartupError("DevTools websocket closed before opening."));
    }),3000,"DevTools websocket startup");
    let sequence=0;
    const pending = new Map();
    socket.onclose = () => {
      for (const [,reject] of pending.values()) reject(new Error("DevTools websocket closed during a command."));
      pending.clear();
    };
    socket.onmessage = event => {
      const response=JSON.parse(event.data);
      if(pending.has(response.id)) {
        const [resolve,reject]=pending.get(response.id); pending.delete(response.id);
        if(response.error) reject(new Error(JSON.stringify(response.error))); else resolve(response.result);
      }
    };
    const call = (method,params={}) => bounded(new Promise((resolve,reject)=>{
      const id=++sequence; pending.set(id,[resolve,reject]); socket.send(JSON.stringify({id,method,params}));
    }),3000,`DevTools command ${method}`);
    closeBrowser = () => call("Browser.close");
    await call("Page.enable");
    await call("Emulation.setDeviceMetricsOverride", {width:Number(width),height:844,deviceScaleFactor:1,mobile:false});
    await call("Emulation.setTouchEmulationEnabled", {enabled:true,maxTouchPoints:5});
    await call("Page.navigate", {url:pathToFileURL(file).href});
    let html="";
    let nativePerformed=false;
    for(let i=0;i<100 && remainingMs()>0;i++) {
      if (!nativePerformed) {
        const actions=await call("Runtime.evaluate",{expression:"window.__moleActions || null",returnByValue:true});
        if(Array.isArray(actions.result.value)) {
          for(const action of actions.result.value) {
            if(action.method) await call(action.method, action.params);
            else await call("Input.dispatchMouseEvent",action);
            await pause(25);
          }
          await call("Runtime.evaluate",{expression:"window.__moleActionsDone=true"});
          nativePerformed=true;
        }
      }
      const result=await call("Runtime.evaluate",{expression:"document.documentElement.outerHTML",returnByValue:true});
      html=result.result.value || "";
      if(html.includes('<pre id="test-results">')) break;
      await pause(50);
    }
    if(!html.includes('<pre id="test-results">')) {
      throw new Error("Browser opened the page but did not produce test-results within 5 seconds.");
    }
    if(screenshot) {
      const result=await call("Page.captureScreenshot",{format:"png",captureBeyondViewport:false});
      fs.writeFileSync(screenshot,Buffer.from(result.data,"base64"));
    }
    return html;
  } finally {
    if(chrome.exitCode === null && chrome.signalCode === null) {
      const closed = new Promise(resolve => chrome.once("close",resolve));
      const timer = setTimeout(() => chrome.kill("SIGKILL"), 3000);
      if(closeBrowser) closeBrowser().catch(()=>{});
      else chrome.kill();
      await closed;
      clearTimeout(timer);
    }
    if(socket) socket.close();
    fs.rmSync(profile,{recursive:true,force:true});
  }
}

async function run() {
  try { return await attempt(); }
  catch(error) {
    if (!(error instanceof StartupError)) throw error;
    process.stderr.write(`Chrome startup failed; retrying once: ${error.message}\n`);
    return await attempt();
  }
}

run().then(html=>process.stdout.write(html))
  .catch(error=>{process.stderr.write(String(error));process.exitCode=1;});
