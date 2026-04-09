"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Cpu, Terminal, Activity, ArrowRight, CheckCircle2, Bot, Calendar, PenBox, MessageCircle, GitBranch, ShieldAlert } from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

type TaskItem = {
  id: string;
  title: string;
  status: string;
};

type FeedEntry = {
  id: string;
  time: string;
  source: string;
  message: string;
  color: string;
  icon: React.ElementType;
};

const AGENT_NODES = [
  { id: "task", label: "Task Manager", icon: CheckCircle2, x: 20, y: 15, color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30" },
  { id: "calendar", label: "Calendar Sync", icon: Calendar, x: 80, y: 15, color: "text-sky-400", bg: "bg-sky-500/10", border: "border-sky-500/30" },
  { id: "notes", label: "Knowledge Base", icon: PenBox, x: 20, y: 85, color: "text-rose-400", bg: "bg-rose-500/10", border: "border-rose-500/30" },
  { id: "comms", label: "Communications", icon: MessageCircle, x: 80, y: 85, color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/30" },
];

export function OrchestratorView() {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [feed, setFeed] = useState<FeedEntry[]>([]);
  const [activeNodes, setActiveNodes] = useState<string[]>([]);

  const addFeedEntry = (source: string, message: string, color: string, icon: React.ElementType) => {
    const time = new Date().toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
    setFeed(prev => [{ id: Math.random().toString(36).slice(2), time, source, message, color, icon }, ...prev].slice(0, 50));
  };

  useEffect(() => {
    addFeedEntry("Orchestrator", "System online. Core agents connected.", "text-[#7b61ff]", Cpu);

    const fetchTasks = async () => {
      try {
        const res = await fetch("/api/tasks");
        const data = await res.json();
        const activeTasks = data.filter((t: TaskItem) => t.status !== "done" && t.status !== "completed");
        
        if (activeTasks.length > 0) {
          addFeedEntry("Orchestrator", `Found ${activeTasks.length} active tasks in system.`, "text-[#7b61ff]", Activity);
          activeTasks.forEach((t: TaskItem) => {
            addFeedEntry("Task Manager", `Active: ${t.title}`, "text-emerald-400", GitBranch);
            // Simulate assigning to nodes based on content loosely, or just globally active
            setActiveNodes(prev => [...new Set([...prev, "task"])]);
          });
          setTasks(activeTasks);
        } else {
          setTasks([]);
        }
      } catch (e) {
        console.error("Could not fetch active tasks", e);
        addFeedEntry("System", "Failed to reach backend", "text-rose-500", ShieldAlert);
      }
    };

    fetchTasks();
    const interval = setInterval(fetchTasks, 10000); // refresh every 10s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col lg:flex-row h-full w-full rounded-3xl border border-white/10 bg-white/5 backdrop-blur-2xl shadow-[0_8px_32px_rgba(0,0,0,0.3)] overflow-hidden">
      
      {/* Network View */}
      <div className="flex-1 relative border-b lg:border-b-0 lg:border-r border-white/10 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-white/10 via-transparent to-black/60 p-8 min-h-[400px]">
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-5 mix-blend-overlay"></div>
        
        <div className="flex items-center gap-3 mb-6 relative z-10">
          <div className="p-2 backdrop-blur-md bg-white/5 border border-white/10 rounded-xl">
            <Cpu className="text-[#7b61ff] w-5 h-5" />
          </div>
          <div>
            <h2 className="text-white font-semibold text-lg drop-shadow-md">TaskForze Central Orchestrator</h2>
            <p className="text-white/40 text-sm">Monitoring cluster state and delegating tasks</p>
          </div>
        </div>

        {/* Node Network Visualizer */}
        <div className="relative w-full h-[calc(100%-80px)] mt-4">
          {/* Central Orchestrator Node */}
          <motion.div 
            className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-28 h-28 rounded-full border-2 border-[#7b61ff]/50 bg-[#7b61ff]/10 flex flex-col items-center justify-center shadow-[0_0_40px_rgba(123,97,255,0.2)] z-20 backdrop-blur-xl"
            animate={{ boxShadow: tasks.length > 0 ? ["0 0 40px rgba(123,97,255,0.2)", "0 0 80px rgba(123,97,255,0.6)", "0 0 40px rgba(123,97,255,0.2)"] : "0 0 40px rgba(123,97,255,0.2)" }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            <Cpu className="w-8 h-8 text-[#7b61ff] mb-1" />
            <span className="text-xs font-bold text-[#bbaaff] uppercase tracking-wider">Core</span>
          </motion.div>

          {/* Lines to subnodes (simplified via SVG) */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none z-10">
            {AGENT_NODES.map((node, i) => {
              const isActive = activeNodes.includes(node.id) || tasks.length > 0;
              return (
                <motion.line
                  key={`line-${node.id}`}
                  x1="50%" y1="50%"
                  x2={`${node.x}%`} y2={`${node.y}%`}
                  stroke={isActive ? "#7b61ff" : "#ffffff"}
                  strokeWidth={isActive ? "2" : "1"}
                  strokeOpacity={isActive ? "0.6" : "0.1"}
                  strokeDasharray={isActive ? "4 4" : "0"}
                  animate={isActive ? { strokeDashoffset: [20, 0] } : {}}
                  transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                />
              );
            })}
          </svg>

          {/* Sub Nodes */}
          {AGENT_NODES.map((node) => {
            const isActive = activeNodes.includes(node.id) || tasks.length > 0;
            return (
              <div 
                key={node.id} 
                className="absolute transform -translate-x-1/2 -translate-y-1/2 z-20 flex flex-col items-center gap-2"
                style={{ left: `${node.x}%`, top: `${node.y}%` }}
              >
                <motion.div 
                  className={cn("w-14 h-14 rounded-2xl border backdrop-blur-lg flex items-center justify-center", node.bg, node.border, isActive && `shadow-[0_0_20px_var(--tw-shadow-color)] shadow-${node.color.split("-")[1]}-500/30`)}
                  animate={{ scale: isActive ? [1, 1.05, 1] : 1 }}
                  transition={{ duration: 2, repeat: Infinity, delay: Math.random() }}
                >
                  <node.icon className={cn("w-6 h-6", node.color)} />
                </motion.div>
                <span className="text-[10px] text-white/50 uppercase tracking-widest font-semibold bg-black/40 px-2 py-1 rounded-md border border-white/5">{node.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Terminal Feed View */}
      <div className="w-full lg:w-[400px] xl:w-[480px] flex flex-col bg-black/40 relative z-20">
        <div className="p-4 border-b border-white/10 flex items-center justify-between bg-white/5 backdrop-blur-md">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-white/40" />
            <h3 className="text-sm font-medium text-white/80 tracking-wide uppercase">System Feed</h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className={cn("animate-ping absolute inline-flex h-full w-full rounded-full opacity-75", tasks.length > 0 ? "bg-emerald-400" : "bg-[#7b61ff]")}></span>
              <span className={cn("relative inline-flex rounded-full h-2 w-2", tasks.length > 0 ? "bg-emerald-500" : "bg-[#7b61ff]")}></span>
            </span>
            <span className="text-xs text-white/40 font-mono">{tasks.length} Active Tasks</span>
          </div>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3 custom-scrollbar">
          <AnimatePresence initial={false}>
            {feed.map((entry) => (
              <motion.div
                key={entry.id}
                initial={{ opacity: 0, x: 20, height: 0 }}
                animate={{ opacity: 1, x: 0, height: "auto" }}
                className="flex items-start gap-3 text-sm border-l-2 border-transparent hover:border-white/10 pl-2 transition-colors"
                style={{ borderLeftColor: entry.color.replace('text-', '') }} // Crude approximation 
              >
                <div className="mt-0.5 shrink-0">
                  <entry.icon className={cn("w-4 h-4", entry.color)} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between mb-0.5">
                    <span className={cn("font-semibold text-xs tracking-wide uppercase", entry.color)}>{entry.source}</span>
                    <span className="text-[10px] text-white/30 font-mono">{entry.time}</span>
                  </div>
                  <p className="text-white/70 leading-snug break-words">{entry.message}</p>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
