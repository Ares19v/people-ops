#!/usr/bin/env node

const BOLD_WHITE = "\x1b[97m\x1b[1m";
const WHITE = "\x1b[97m";
const DIM_WHITE = "\x1b[37m";
const RESET = "\x1b[0m";

const banner = `
${BOLD_WHITE}   _____  ______ ____  _____  _      ______ ____  _____   _____ 
  |  __ \\|  ____/ __ \\|  __ \\| |    |  ____/ __ \\|  __ \\ / ____|
  | |__) | |__ | |  | | |__) | |    | |__ | |  | | |__) | (___  
  |  ___/|  __|| |  | |  ___/| |    |  __|| |  | |  ___/ \\___ \\ 
  | |    | |___| |__| | |    | |____| |___| |__| | |     ____) |
  |_|    |______\\____/|_|    |______|______\\____/|_|    |_____/ 
${WHITE}                                                     HRMS FLEET v2.0
${BOLD_WHITE}  ====================================================================
   * ENTERPRISE MULTI-AGENT FLEET & ADK OBSERVABILITY PLATFORM *
  ====================================================================${WHITE}
   [•] API Backend     : ${BOLD_WHITE}http://127.0.0.1:8000${WHITE} (FastAPI / LangGraph)
   [•] Web Portal      : ${BOLD_WHITE}http://localhost:5173${WHITE} (Vite SPA Dashboard)
   [•] ngrok Tunnel    : ${BOLD_WHITE}https://upcountry-scarcity-hatchery.ngrok-free.dev${WHITE}
   [•] LLM Judges      : ${BOLD_WHITE}Langfuse Benchmark (25 Prompts / 6 Evaluators)${WHITE}
${BOLD_WHITE}  ====================================================================${DIM_WHITE}
   Press [Ctrl+C] at any time to shut down all processes cleanly.
${RESET}`;

console.log(banner);
