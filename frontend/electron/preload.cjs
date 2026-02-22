const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("aiAgentDesktop", {
  platform: process.platform,
});
