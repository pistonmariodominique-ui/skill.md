"""SwingBot AI — bot de trading swing/position semi-autonome.

Basé sur SPECS_SWINGBOT.md v1.0 (Mario Piston + Jarvis).
Hérite des composants validés de ForexBot AI : connecteur Capital.com,
kill-switch, sizing sur stop broker réel, réconciliation, Telegram, dashboard.

Principes non négociables (section 2 des specs) :
- aucun ordre sans stop-loss broker confirmé ;
- aucune martingale, aucun grid averaging ;
- l'IA n'a jamais le pouvoir d'ordre : le moteur déterministe décide ;
- abstention par défaut en cas de doute.
"""

__version__ = "1.0.0"
