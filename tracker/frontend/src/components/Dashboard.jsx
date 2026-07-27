import { useState, useEffect } from 'react';
import {
  LayoutDashboard, Heart, FileText, Calendar, CircleCheckBig, X,
  TrendingUp, Bot, Activity,
} from 'lucide-react';
import { fetchStats } from '../api';
import ActivityFeed from './ActivityFeed';

const STAT_CARDS = [
  { key: 'saved', label: 'Saved', icon: Heart, color: 'text-[#294A73]', bg: 'bg-[#DCE8F3]' },
  { key: 'applied', label: 'Applied', icon: FileText, color: 'text-[#117D84]', bg: 'bg-[#CEF2F1]' },
  { key: 'interviewing', label: 'Interviewing', icon: Calendar, color: 'text-[#23677C]', bg: 'bg-[#D7EDF1]' },
  { key: 'offered', label: 'Offered', icon: CircleCheckBig, color: 'text-[#177663]', bg: 'bg-[#CDEEE4]' },
  { key: 'rejected', label: 'Rejected', icon: X, color: 'text-[#A34C5A]', bg: 'bg-[#F2DDE1]' },
];

export default function Dashboard() {
  const [stats, setStats] = useState({ saved: 0, applied: 0, interviewing: 0, offered: 0, rejected: 0, total: 0 });

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchStats();
        setStats(data);
      } catch (err) {
        console.error('Failed to fetch stats:', err);
      }
    };
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#18B8BC] to-[#117D84] shadow-md">
          <Bot className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-[#203A5F]">Agent Dashboard</h1>
          <p className="text-sm text-[#708198]">Overview of all agent operations and job tracking</p>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {/* Total card */}
        <div className="rounded-xl border border-[#DCE5ED] bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#18B8BC] to-[#117D84]">
              <TrendingUp className="h-4 w-4 text-white" />
            </div>
            <span className="text-xs font-medium text-[#8291A5]">Total</span>
          </div>
          <p className="mt-2 text-2xl font-bold text-[#203A5F]">{stats.total}</p>
        </div>

        {/* Per-stage cards */}
        {STAT_CARDS.map(({ key, label, icon: Icon, color, bg }) => (
          <div key={key} className="rounded-xl border border-[#DCE5ED] bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2">
              <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${bg}`}>
                <Icon className={`h-4 w-4 ${color}`} />
              </div>
              <span className="text-xs font-medium text-[#8291A5]">{label}</span>
            </div>
            <p className={`mt-2 text-2xl font-bold ${color}`}>{stats[key]}</p>
          </div>
        ))}
      </div>

      {/* Activity Feed — full width, last 30 events */}
      <div>
        <div className="mb-3 flex items-center gap-2">
          <Activity className="h-5 w-5 text-[#18B8BC]" />
          <h2 className="text-lg font-semibold text-[#203A5F]">Live Activity</h2>
        </div>
        <ActivityFeed compact={false} limit={30} />
      </div>
    </div>
  );
}
