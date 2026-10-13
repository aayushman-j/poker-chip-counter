"""Poker Chip Counter - track chips, pots and winners across rounds.

Flow:
  1. Setup: value of 1 chip (in rupees), number of players, starting chips.
  2. Each round: enter the chips every player put in, pick the winner.
     The winner receives the whole pot; everyone else loses what they put in.
  3. Standings, history and settings (rebuy, undo, reset) live in tabs.

Game data lives in st.session_state only (it is lost on refresh).
"""

import html

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Poker Chip Counter", page_icon="🪙", layout="centered")

RESERVED_NAMES = {"Event", "Winner", "Pot (chips)", "Pot (₹)"}

CSS = """
<style>



.block-container {
    padding-top: 1.5rem;
    max-width: 720px;
    width: 100%;
    box-sizing: border-box;
}



.title {
    text-align: center;
    font-family: Georgia, 'Times New Roman', serif;
    font-size: clamp(1.35rem, 5vw, 2rem);
    line-height: 1.3;
    color: #D4AF37;
    margin: 0 auto 0.2rem;
    width: 100%;
    max-width: 100%;
    overflow-wrap: anywhere;
    box-sizing: border-box;
}

         
.subtitle { text-align:center; opacity:.8; margin-bottom: 1rem; }
.topbar { display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap;
          background:#0F4D3A; border:1px solid rgba(212,175,55,.45);
          border-radius:12px; padding:10px 14px; margin-bottom:12px; }
.topbar b { color:#D4AF37; }
.player-card { background:#0F4D3A; border:1px solid rgba(212,175,55,.35);
               border-radius:14px; padding:14px 16px; margin-bottom:10px; }
.player-card.leader { border:2px solid #D4AF37; box-shadow:0 0 14px rgba(212,175,55,.35); }
.player-card .name { font-size:1.1rem; font-weight:700; }
.player-card .chips { font-size:1.9rem; font-weight:800; color:#D4AF37; line-height:1.2; }
.player-card .muted { opacity:.8; font-size:.88rem; }
.up { color:#5CE08A; font-weight:700; }
.down { color:#FF7B7B; font-weight:700; }
.flat { opacity:.75; }
.stButton > button { border-radius:10px; font-weight:700; }
div[data-testid="stMetric"] { background:#0F4D3A; border:1px solid rgba(212,175,55,.35);
                              border-radius:12px; padding:8px 12px; }

.footer-hr { border:none; height:1px; margin:2.5rem 0 1rem;
             background:linear-gradient(90deg, transparent, #D4AF37, transparent); }
.footer { text-align:center; line-height:1.7; padding-bottom:1rem; }
.footer .copy { font-family:'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                font-size:.8rem; letter-spacing:1.5px; text-transform:uppercase; opacity:.85; }
.footer .tag { font-family:Georgia, 'Times New Roman', serif; font-style:italic;
               font-size:1rem; color:#D4AF37; margin-top:.2rem; }
</style>
"""


# ----------------------------------------------------------------- helpers
def esc(value) -> str:
    return html.escape(str(value))


def inr(amount: float) -> str:
    return f"₹{amount:,.2f}"


def signed_inr(amount: float) -> str:
    if round(amount, 2) == 0:
        return "₹0.00"
    return f"{'+' if amount > 0 else '−'}₹{abs(amount):,.2f}"


def signed(n: int) -> str:
    return "0" if n == 0 else f"{n:+d}".replace("-", "−")


def tone(n: float) -> str:
    return "up" if n > 0 else "down" if n < 0 else "flat"


def rounds_played(game: dict) -> int:
    return sum(1 for e in game["log"] if e["type"] == "round")


# --------------------------------------------------------------- game state
def new_game(chip_value: float, names: list[str], starting: int) -> None:
    st.session_state.game = {
        "chip_value": chip_value,
        "players": names,
        "starting": starting,
        "balances": {n: starting for n in names},
        "buyins": {n: starting for n in names},  # total chips each player bought in
        "log": [],  # every round / rebuy, with balances after the event
    }


def undo_last(game: dict) -> None:
    if not game["log"]:
        return
    game["log"].pop()
    if game["log"]:
        last = game["log"][-1]
        game["balances"] = dict(last["balances"])
        game["buyins"] = dict(last["buyins"])
    else:
        game["balances"] = {p: game["starting"] for p in game["players"]}
        game["buyins"] = {p: game["starting"] for p in game["players"]}


def reset_game() -> None:
    st.session_state.game = None
    st.session_state.confirm_reset = False

def footer() -> None:
    st.markdown(
        '<hr class="footer-hr">'
        '<div class="footer">'
        '<div class="copy">© Aayushman &nbsp;|&nbsp; NIT M</div>'
        '<div class="tag">Shuffle up and play ♠ ♥ ♦ ♣</div>'
        '</div>',
        unsafe_allow_html=True,
    )                                              


# ------------------------------------------------------------------- setup
def setup_screen() -> None:
    st.markdown('<div class="title">♠ Poker Chip Counter ♥</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Set up your table</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    chip_value = c1.number_input("1 chip = ₹", min_value=0.01, value=10.0, step=1.0, format="%.2f")
    starting = c2.number_input("Starting chips per player", min_value=1, value=100, step=10)
    n_players = st.slider("Number of players", min_value=2, max_value=10, value=4)

    st.write("**Player names**")
    cols = st.columns(2)
    names = []
    for i in range(n_players):
        default = f"Player {i + 1}"
        names.append(cols[i % 2].text_input(f"Player {i + 1}", value=default, key=f"name_{i}").strip())

    st.caption(f"Each player starts with {starting} chips = {inr(starting * chip_value)}")

    if st.button("Start Game 🎲", type="primary", width="stretch"):
        if any(not n for n in names):
            st.error("Every player needs a name.")
        elif len(set(n.lower() for n in names)) != len(names):
            st.error("Player names must be unique.")
        elif any(n in RESERVED_NAMES for n in names):
            st.error("Please pick a different name (that one is reserved).")
        else:
            new_game(float(chip_value), names, int(starting))
            st.rerun()


# --------------------------------------------------------------------- play
def play_tab(game: dict) -> None:
    players, balances, cv = game["players"], game["balances"], game["chip_value"]
    rnd = rounds_played(game) + 1

    if sum(1 for p in players if balances[p] > 0) < 2:
        st.warning("Fewer than two players have chips left. Add chips in Settings or reset the game.")

    st.subheader(f"Round {rnd}")
    st.caption("Enter how many chips each player put into the pot this round.")

    bets = {}
    cols = st.columns(2)
    for i, p in enumerate(players):
        bal = balances[p]
        with cols[i % 2]:
            if bal <= 0:
                st.markdown(f"**{esc(p)}** - out of chips")
                bets[p] = 0
            else:
                bets[p] = st.number_input(
                    f"{p} (has {bal})", min_value=0, max_value=bal, value=0, step=1, key=f"bet_{rnd}_{p}"
                )

    pot = sum(bets.values())
    m1, m2 = st.columns(2)
    m1.metric("Pot (chips)", pot)
    m2.metric("Pot (₹)", inr(pot * cv))

    contenders = [p for p in players if bets[p] > 0]
    winner = st.selectbox(
        "Who won this round?",
        contenders,
        index=None,
        placeholder="Pick the winner" if contenders else "Enter some bets first",
        key=f"winner_{rnd}",
    )

    if st.button("Confirm Round ✅", type="primary", width="stretch"):
        if pot <= 0:
            st.error("The pot is empty. Enter at least one bet.")
        elif winner is None:
            st.error("Pick who won the round.")
        else:
            deltas = {p: -bets[p] for p in players}
            deltas[winner] += pot
            for p in players:
                balances[p] += deltas[p]
            game["log"].append(
                {
                    "type": "round",
                    "round": rnd,
                    "bets": dict(bets),
                    "pot": pot,
                    "winner": winner,
                    "deltas": deltas,
                    "balances": dict(balances),
                    "buyins": dict(game["buyins"]),
                }
            )
            st.session_state.flash = (
                f"🏆 {winner} won Round {rnd} and takes {pot} chips ({inr(pot * cv)}). "
                f"Net {signed(deltas[winner])} chips."
            )
            st.rerun()


# ---------------------------------------------------------------- standings
def standings_tab(game: dict) -> None:
    players, balances, buyins, cv = game["players"], game["balances"], game["buyins"], game["chip_value"]
    played = rounds_played(game)
    last_round = next((e for e in reversed(game["log"]) if e["type"] == "round"), None)
    top = max(balances.values())

    for p in sorted(players, key=lambda x: balances[x], reverse=True):
        bal = balances[p]
        net_chips = bal - buyins[p]
        last_delta = last_round["deltas"].get(p, 0) if last_round else 0
        is_leader = played > 0 and bal == top and top > 0
        won_last = last_round is not None and last_round["winner"] == p

        badges = ("👑 " if is_leader else "") + esc(p) + (" 🏆" if won_last else "")
        last_txt = (
            f'last round <span class="{tone(last_delta)}">{"▲" if last_delta > 0 else "▼" if last_delta < 0 else "•"} '
            f"{signed(last_delta)}</span> · "
            if last_round
            else ""
        )
        st.markdown(
            f"""
            <div class="player-card {'leader' if is_leader else ''}">
              <div class="name">{badges}</div>
              <div class="chips">🪙 {bal}</div>
              <div class="muted">{inr(bal * cv)} · {last_txt}overall
                <span class="{tone(net_chips)}">{signed_inr(net_chips * cv)}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ------------------------------------------------------------------ history
def history_tab(game: dict) -> None:
    players, cv = game["players"], game["chip_value"]
    if not game["log"]:
        st.info("No rounds yet. Play a round and it will show up here.")
        return

    rows = []
    for e in game["log"]:
        if e["type"] == "round":
            row = {"Event": f"Round {e['round']}", "Winner": e["winner"],
                   "Pot (chips)": e["pot"], "Pot (₹)": round(e["pot"] * cv, 2)}
            row.update(e["deltas"])
        else:
            row = {"Event": "Rebuy", "Winner": "-", "Pot (chips)": None, "Pot (₹)": None}
            row.update({p: (e["chips"] if p == e["player"] else 0) for p in players})
        rows.append(row)
    st.write("**Round log** (chip change per player)")
    st.dataframe(pd.DataFrame(rows[::-1]), hide_index=True, width="stretch")

    start = {p: game["starting"] for p in players}
    timeline = pd.DataFrame([start] + [e["balances"] for e in game["log"]])
    st.write("**Chips over time**")
    st.line_chart(timeline)
    st.caption("x-axis: 0 = start, then each round or rebuy in order.")


# ----------------------------------------------------------------- settings
def settings_tab(game: dict) -> None:
    players, cv = game["players"], game["chip_value"]

    st.write("**Rebuy / add chips**")
    p = st.selectbox("Player", players, key="rebuy_player")
    amount = st.number_input("Chips to add", min_value=1, value=game["starting"], step=10, key="rebuy_amount")
    st.caption(f"{amount} chips = {inr(amount * cv)}")
    if st.button("Add chips 🪙", width="stretch"):
        game["balances"][p] += int(amount)
        game["buyins"][p] += int(amount)
        game["log"].append(
            {
                "type": "rebuy",
                "player": p,
                "chips": int(amount),
                "balances": dict(game["balances"]),
                "buyins": dict(game["buyins"]),
            }
        )
        st.session_state.flash = f"{p} added {int(amount)} chips ({inr(amount * cv)})."
        st.rerun()

    st.divider()
    st.write("**Undo**")
    last = game["log"][-1] if game["log"] else None
    if last is None:
        st.caption("Nothing to undo yet.")
    elif last["type"] == "round":
        st.caption(f"Last action: Round {last['round']}, won by {last['winner']} ({last['pot']} chips).")
    else:
        st.caption(f"Last action: rebuy of {last['chips']} chips by {last['player']}.")
    if st.button("↩️ Undo last action", disabled=last is None, width="stretch"):
        undo_last(game)
        st.session_state.flash = "Last action undone."
        st.rerun()

    st.divider()
    st.write("**Game**")
    st.caption(f"1 chip = {inr(cv)} · {len(players)} players · started with {game['starting']} chips each")
    st.checkbox("I want to end this game and start over", key="confirm_reset")
    st.button(
        "🗑️ Reset game",
        disabled=not st.session_state.get("confirm_reset", False),
        on_click=reset_game,
        width="stretch",
    )


# --------------------------------------------------------------------- main
def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    if st.session_state.get("game") is None:
        setup_screen()
        footer()
        return

    game = st.session_state.game
    st.divider()
    st.markdown('<div class="title">♠ ♥ Poker Chip Counter ♦ ♣</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="topbar"><span>Round <b>{rounds_played(game) + 1}</b></span>'
        f'<span>1 chip = <b>{inr(game["chip_value"])}</b></span>'
        f'<span>Chips on table <b>{sum(game["balances"].values())}</b></span></div>',
        unsafe_allow_html=True,
    )

    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))

    tab_play, tab_stand, tab_hist, tab_set = st.tabs(["🎴 Play", "🏆 Standings", "📜 History", "⚙️ Settings"])
    with tab_play:
        play_tab(game)
    with tab_stand:
        standings_tab(game)
    with tab_hist:
        history_tab(game)
    with tab_set:
        settings_tab(game)

    footer()


main()
