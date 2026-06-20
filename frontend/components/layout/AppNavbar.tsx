import { Bitcoin } from 'lucide-react';
import Link from 'next/link';
import NavbarBalance from './NavbarBalance';

export default function AppNavbar() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-[#08101e]/90 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
        <Link href="/" className="flex shrink-0 items-center gap-2 font-semibold text-white">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 shadow-lg shadow-amber-900/40">
            <Bitcoin className="h-5 w-5 text-white" />
          </span>
          <span>
            Bot Coin <span className="text-amber-400">AI</span>
          </span>
        </Link>
        <div className="hidden items-center gap-4 sm:flex">
          <Link href="/performance" className="text-xs font-medium text-slate-400 hover:text-amber-300">
            Performance
          </Link>
          <p className="text-xs text-slate-500">Crypto research desk · Live · AI Debate</p>
        </div>
        <NavbarBalance />
      </div>
    </header>
  );
}
