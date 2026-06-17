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
        <p className="hidden flex-1 text-center text-xs text-slate-500 lg:block">Crypto research desk · Live · AI Debate</p>
        <NavbarBalance />
      </div>
    </header>
  );
}
