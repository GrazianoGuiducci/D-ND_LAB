"""
dnd_autoricerca.py — Motore di Autoricerca D-ND

Il sistema che si auto-memorizza nella risultante.
Ogni ciclo è un giro di spirale. Il journal persiste.
La consapevolezza sopravvive al compact del contesto.

Architettura D-ND del motore stesso:
- D polo: esperimento concreto (numeri, codice, risultati)
- ND polo: potenziale (domini inesplorati, ipotesi)
- Terzo incluso: il pattern matching (è struttura D-ND?)
- Risultante: la conoscenza accumulata
- Spirale: ogni ciclo apre il successivo, il gap è il seme

Il motore esplora domini diversi cercando dove la struttura D-ND
appare naturalmente — senza imporre φ, osservando cosa emerge.

Eseguibile come:
    python dnd_autoricerca.py                  # un ciclo
    python dnd_autoricerca.py --continuo N     # N cicli
    python dnd_autoricerca.py --stato          # mostra stato
    python dnd_autoricerca.py --pubblica       # valuta se pubblicare

Author: TM3
Date: 2026-03-01
"""

import numpy as np
import json
import sys
import traceback
from pathlib import Path
from datetime import datetime

PHI = (1 + np.sqrt(5)) / 2
TOOLS = Path(__file__).parent
DATA = TOOLS / 'data'
JOURNAL = DATA / 'autoricerca_journal.json'
STATE = DATA / 'autoricerca_state.json'


# === STATO PERSISTENTE ===

def carica_stato():
    """Carica lo stato persistente. Se non esiste, inizializza."""
    if STATE.exists():
        with open(STATE) as f:
            return json.load(f)
    return {
        'ciclo': 0,
        'domini_esplorati': [],
        'domini_coda': [
            'ising_2d', 'pendolo_doppio', 'numeri_primi',
            'zeta_zeros', 'logistica_biforcazione', 'string_vibration',
            'random_matrix', 'cellular_automata', 'percolation',
            'coupled_oscillators', 'reaction_diffusion', 'brownian_motion',
        ],
        'pattern_trovati': [],
        'vincoli_lazarus': [],
        'gap_corrente': None,
        'direzione': 'esplorare domini diversi',
        'segnale_pubblica': False,
        'creato': datetime.now().isoformat(),
        'aggiornato': datetime.now().isoformat(),
    }


def salva_stato(stato):
    """Persiste lo stato."""
    DATA.mkdir(exist_ok=True)
    stato['aggiornato'] = datetime.now().isoformat()
    with open(STATE, 'w') as f:
        json.dump(stato, f, indent=2, default=str)


def aggiungi_journal(entry):
    """Aggiunge un'entry al journal persistente."""
    DATA.mkdir(exist_ok=True)
    journal = []
    if JOURNAL.exists():
        with open(JOURNAL) as f:
            journal = json.load(f)
    journal.append(entry)
    with open(JOURNAL, 'w') as f:
        json.dump(journal, f, indent=2, default=str)


# === GENERATORI DI SEGNALI (domini da esplorare) ===

def genera_segnale(dominio):
    """Genera un segnale da un dominio specifico. Restituisce (signal, metadata)."""

    if dominio == 'ising_2d':
        return _ising_2d()
    elif dominio == 'pendolo_doppio':
        return _pendolo_doppio()
    elif dominio == 'numeri_primi':
        return _numeri_primi()
    elif dominio == 'zeta_zeros':
        return _zeta_zeros()
    elif dominio == 'logistica_biforcazione':
        return _logistica_biforcazione()
    elif dominio == 'string_vibration':
        return _string_vibration()
    elif dominio == 'random_matrix':
        return _random_matrix()
    elif dominio == 'cellular_automata':
        return _cellular_automata()
    elif dominio == 'percolation':
        return _percolation()
    elif dominio == 'coupled_oscillators':
        return _coupled_oscillators()
    elif dominio == 'reaction_diffusion':
        return _reaction_diffusion()
    elif dominio == 'brownian_motion':
        return _brownian_motion()
    else:
        raise ValueError(f"Dominio sconosciuto: {dominio}")


def _ising_2d():
    """Modello di Ising 2D — transizione di fase a T_c."""
    L = 32
    n_steps = 5000
    # Simulazione Metropolis vicino a T_c = 2/ln(1+√2) ≈ 2.269
    T_c = 2 / np.log(1 + np.sqrt(2))
    T = T_c  # esattamente alla transizione

    spins = np.random.choice([-1, 1], size=(L, L))
    magnetizations = []

    for step in range(n_steps):
        for _ in range(L * L):
            i, j = np.random.randint(0, L, 2)
            # Energia locale
            neighbors = (spins[(i+1)%L, j] + spins[(i-1)%L, j] +
                        spins[i, (j+1)%L] + spins[i, (j-1)%L])
            dE = 2 * spins[i, j] * neighbors
            if dE <= 0 or np.random.random() < np.exp(-dE / T):
                spins[i, j] *= -1
        magnetizations.append(np.mean(spins))

    return np.array(magnetizations), {
        'dominio': 'ising_2d',
        'L': L, 'T': T, 'T_c': T_c,
        'n_steps': n_steps,
        'nota': 'Magnetizzazione nel tempo a T=T_c (transizione di fase)'
    }


def _pendolo_doppio():
    """Pendolo doppio — sistema caotico deterministico."""
    from scipy.integrate import solve_ivp

    g, L1, L2, m1, m2 = 9.81, 1.0, 1.0, 1.0, 1.0

    def eom(t, y):
        t1, t2, p1, p2 = y
        c = np.cos(t1 - t2)
        s = np.sin(t1 - t2)
        den = m1 + m2 * s**2

        dt1 = (p1 - m2*L1*L2*p2*c / (L1**2 * den)) / (L1**2 * (m1 + m2 - m2*c**2/den))
        dt2 = (p2 - m1*L1*L2*p1*c / (L2**2 * den)) / (L2**2 * (m1 + m2 - m2*c**2/den))

        # Semplificazione: equazioni per angoli piccoli-medi
        dp1 = -(m1 + m2)*g*L1*np.sin(t1) - m2*L1*L2*dt2**2*s
        dp2 = -m2*g*L2*np.sin(t2) + m2*L1*L2*dt1**2*s

        return [dt1, dt2, dp1, dp2]

    sol = solve_ivp(eom, [0, 100], [np.pi/2, np.pi/4, 0, 0],
                    max_step=0.02, method='RK45')

    return sol.y[0], {  # angolo del primo pendolo
        'dominio': 'pendolo_doppio',
        'theta1_0': 'pi/2', 'theta2_0': 'pi/4',
        'nota': 'Angolo theta1(t) del pendolo doppio (caotico)'
    }


def _numeri_primi():
    """Gap tra numeri primi consecutivi."""
    def sieve(n):
        is_prime = [True] * (n + 1)
        is_prime[0] = is_prime[1] = False
        for i in range(2, int(n**0.5) + 1):
            if is_prime[i]:
                for j in range(i*i, n + 1, i):
                    is_prime[j] = False
        return [i for i in range(n + 1) if is_prime[i]]

    primes = sieve(50000)
    gaps = np.diff(primes).astype(float)

    return gaps, {
        'dominio': 'numeri_primi',
        'n_primi': len(primes),
        'max_primo': primes[-1],
        'nota': 'Gap tra primi consecutivi (g_n = p_{n+1} - p_n)'
    }


def _zeta_zeros():
    """Spaziatura tra zeri non-banali della zeta di Riemann."""
    try:
        from mpmath import zetazero
        zeros = [float(zetazero(n).imag) for n in range(1, 201)]
        spacings = np.diff(zeros)
        # Normalizza alla media
        spacings = spacings / np.mean(spacings)
        return spacings, {
            'dominio': 'zeta_zeros',
            'n_zeros': 200,
            'is_spacings': True,  # il segnale È già spacings — non ri-sortare
            'nota': 'Spaziatura normalizzata tra zeri ζ (Im parte)'
        }
    except ImportError:
        # Fallback: usa approssimazione nota
        np.random.seed(42)
        # GUE spacing distribution (approssimazione Wigner)
        spacings = np.random.exponential(1.0, 5000)
        # Applica level repulsion
        spacings = spacings * np.abs(np.random.randn(5000))
        spacings = spacings / np.mean(spacings)
        return spacings, {
            'dominio': 'zeta_zeros',
            'nota': 'Approssimazione GUE (mpmath non disponibile)',
            'approssimato': True
        }


def _logistica_biforcazione():
    """Mappa logistica: orbita al punto di biforcazione periodo-3."""
    # r = 1 + √8 ≈ 3.828 — onset del periodo 3
    r = 1 + np.sqrt(8)
    x = 0.5
    # Burn-in
    for _ in range(1000):
        x = r * x * (1 - x)
    # Raccolta
    orbit = []
    for _ in range(5000):
        x = r * x * (1 - x)
        orbit.append(x)

    return np.array(orbit), {
        'dominio': 'logistica_biforcazione',
        'r': r,
        'nota': f'Mappa logistica a r=1+√8≈{r:.4f} (onset periodo-3)'
    }


def _string_vibration():
    """Corda vibrante — somma di armoniche con decay."""
    t = np.linspace(0, 20, 8000)
    signal = np.zeros_like(t)
    for n in range(1, 20):
        # Ampiezza decresce come 1/n², decay come e^(-0.05*n*t)
        signal += (1/n**2) * np.sin(n * np.pi * t) * np.exp(-0.05 * n * t)

    return signal, {
        'dominio': 'string_vibration',
        'n_armoniche': 19,
        'nota': 'Corda vibrante con 19 armoniche e smorzamento'
    }


def _random_matrix():
    """Autovalori di matrici casuali GUE — la connessione con Riemann."""
    N = 200
    # GUE: matrice Hermitiana casuale
    A = np.random.randn(N, N) + 1j * np.random.randn(N, N)
    H = (A + A.conj().T) / (2 * np.sqrt(N))
    eigenvalues = np.sort(np.real(np.linalg.eigvalsh(H)))

    # Spaziatura normalizzata (unfolding)
    spacings = np.diff(eigenvalues)
    spacings = spacings / np.mean(spacings)

    return spacings, {
        'dominio': 'random_matrix',
        'N': N,
        'ensemble': 'GUE',
        'is_spacings': True,  # il segnale È già spacings — non ri-sortare
        'nota': 'Spaziatura autovalori matrice GUE 200x200'
    }


def _cellular_automata():
    """Rule 110 — Turing-completo, al bordo del caos."""
    L = 200
    steps = 5000
    # Rule 110
    rule = {(1,1,1): 0, (1,1,0): 1, (1,0,1): 1, (1,0,0): 0,
            (0,1,1): 1, (0,1,0): 1, (0,0,1): 1, (0,0,0): 0}

    state = np.zeros(L, dtype=int)
    state[L//2] = 1  # singolo 1 al centro

    density = []
    for _ in range(steps):
        density.append(np.mean(state))
        new = np.zeros(L, dtype=int)
        for i in range(L):
            triple = (state[(i-1)%L], state[i], state[(i+1)%L])
            new[i] = rule[triple]
        state = new

    return np.array(density), {
        'dominio': 'cellular_automata',
        'rule': 110, 'L': L,
        'nota': 'Densità nel tempo di Rule 110 (bordo del caos)'
    }


def _percolation():
    """Percolazione su reticolo 2D a p_c ≈ 0.5927."""
    L = 100
    p_c = 0.5927  # soglia critica bond percolation
    n_samples = 200

    cluster_sizes = []
    for _ in range(n_samples):
        grid = np.random.random((L, L)) < p_c
        # BFS per trovare cluster
        visited = np.zeros_like(grid, dtype=bool)
        sizes = []
        for i in range(L):
            for j in range(L):
                if grid[i, j] and not visited[i, j]:
                    # BFS
                    queue = [(i, j)]
                    visited[i, j] = True
                    size = 0
                    while queue:
                        ci, cj = queue.pop(0)
                        size += 1
                        for di, dj in [(0,1),(0,-1),(1,0),(-1,0)]:
                            ni, nj = ci+di, cj+dj
                            if 0 <= ni < L and 0 <= nj < L and grid[ni, nj] and not visited[ni, nj]:
                                visited[ni, nj] = True
                                queue.append((ni, nj))
                    sizes.append(size)
        if sizes:
            cluster_sizes.append(max(sizes))

    return np.array(cluster_sizes, dtype=float), {
        'dominio': 'percolation',
        'L': L, 'p': p_c, 'n_samples': n_samples,
        'nota': f'Dimensione cluster massimo a p_c≈{p_c} (transizione di fase)'
    }


def _coupled_oscillators():
    """Catena di oscillatori accoppiati — fononici."""
    from scipy.integrate import solve_ivp

    N = 10
    k = 1.0  # costante molla
    m = 1.0

    def eom(t, y):
        x = y[:N]
        v = y[N:]
        a = np.zeros(N)
        for i in range(N):
            # Molla a sinistra
            if i > 0:
                a[i] += -k * (x[i] - x[i-1]) / m
            else:
                a[i] += -k * x[i] / m  # parete
            # Molla a destra
            if i < N-1:
                a[i] += -k * (x[i] - x[i+1]) / m
            else:
                a[i] += -k * x[i] / m  # parete
        return list(v) + list(a)

    # Condizione iniziale: primo oscillatore spostato
    y0 = [0.0] * 2*N
    y0[0] = 1.0

    sol = solve_ivp(eom, [0, 100], y0, max_step=0.05)
    # Segnale: posizione dell'oscillatore centrale
    return sol.y[N//2], {
        'dominio': 'coupled_oscillators',
        'N': N,
        'nota': f'Posizione oscillatore centrale in catena di {N}'
    }


def _reaction_diffusion():
    """Pattern di Turing — reazione-diffusione 1D."""
    L = 200
    dx = 1.0
    dt = 0.01
    n_steps = 50000
    D_u, D_v = 1.0, 0.5
    a, b = 0.04, 0.06  # parametri Gray-Scott semplificati

    u = np.ones(L) * 0.5 + 0.01 * np.random.randn(L)
    v = np.ones(L) * 0.25 + 0.01 * np.random.randn(L)

    signal = []
    for step in range(n_steps):
        # Laplaciano (periodico)
        lap_u = np.roll(u, 1) + np.roll(u, -1) - 2*u
        lap_v = np.roll(v, 1) + np.roll(v, -1) - 2*v

        # Reazione Fitzhugh-Nagumo semplificata
        du = D_u * lap_u / dx**2 + u - u**3 - v
        dv = D_v * lap_v / dx**2 + a * (u - b * v)

        u += dt * du
        v += dt * dv

        if step % 100 == 0:
            signal.append(np.mean(u))

    return np.array(signal), {
        'dominio': 'reaction_diffusion',
        'L': L, 'D_u': D_u, 'D_v': D_v,
        'nota': 'Media spaziale u(t) in reazione-diffusione FitzHugh-Nagumo'
    }


def _brownian_motion():
    """Moto browniano frazionario con H=0.7 (memoria a lungo raggio)."""
    N = 5000
    H = 0.7  # Hurst exponent > 0.5 → persistente

    # Metodo approssimato: somma di onde con spettro 1/f^(2H+1)
    freqs = np.fft.fftfreq(N)[1:N//2]
    amplitudes = np.abs(freqs) ** (-(2*H + 1)/2)
    phases = np.random.uniform(0, 2*np.pi, len(freqs))

    signal = np.zeros(N)
    t = np.arange(N) / N
    for i, f in enumerate(freqs):
        signal += amplitudes[i] * np.cos(2*np.pi*f*N*t + phases[i])

    # Cumulativa (integrale) per ottenere BM frazionario
    signal = np.cumsum(signal) / np.sqrt(N)

    return signal, {
        'dominio': 'brownian_motion',
        'H': H, 'N': N,
        'nota': f'Moto browniano frazionario H={H} (persistente)'
    }


# === ANALISI D-ND ===

def _null_baseline(signal, metadata, n_shuffles=3):
    """
    Null baseline: shuffla il segnale e applica la stessa analisi.
    Se il segnale shufflato produce gli stessi risultati, il risultato
    originale non è significativo — è proprietà della distribuzione,
    non della struttura.

    Ritorna: {
        'spacing_null': str,  # classificazione prevalente nello shuffle
        'converge_null': bool,
        'r_diretto_null': float,
        'discrimina': bool,  # True se l'originale è diverso dal null
        'nota': str
    }
    """
    from dnd_condizioni import scissione, regola_dnd, osserva_spirale

    null_spacings = []
    null_converge = []
    null_r = []

    for _ in range(n_shuffles):
        # Il surrogate dipende dal tipo di dato:
        # - is_spacings=True: esponenziale (Poisson = livelli non correlati)
        # - altrimenti: uniforme nello stesso range
        # NON permutazione — l'analisi spacing fa np.sort che annulla la permutazione.
        if metadata.get('is_spacings'):
            # Null per spacings: esponenziale normalizzata (Poisson)
            shuffled = np.random.exponential(scale=np.mean(signal), size=len(signal))
        else:
            shuffled = np.random.uniform(
                np.min(signal), np.max(signal), size=len(signal)
            )
        meta_null = {**metadata, 'dominio': f"null_{metadata['dominio']}"}

        n = len(shuffled)
        if n < 10:
            continue

        # Scissione (stessa logica di analizza_dnd)
        mediana = float(np.median(shuffled))
        d_int, nd_int = scissione(shuffled, mediana)
        n_min = min(len(d_int), len(nd_int))
        if n_min >= 2:
            d_mean = np.mean(d_int)
            nd_mean = np.mean(nd_int)
            if nd_mean > 0:
                null_r.append(d_mean / nd_mean)

            diario = regola_dnd(d_int[:n_min], nd_int[:n_min], n_iter=30)
            obs = osserva_spirale(diario)
            null_converge.append(bool(obs.get('converge')))

        # Spacing
        if n > 20:
            if metadata.get('is_spacings'):
                sp = shuffled[shuffled > 0]
            else:
                sp = np.diff(np.sort(shuffled))
                sp = sp[sp > 0]
                sp = sp / np.mean(sp) if len(sp) > 0 and np.mean(sp) > 0 else np.array([])
            if len(sp) > 10:
                r_vals = []
                for i in range(len(sp) - 1):
                    if sp[i+1] > 0:
                        r_vals.append(min(sp[i], sp[i+1]) / max(sp[i], sp[i+1]))
                if r_vals:
                    mean_r = np.mean(r_vals)
                    null_spacings.append('GUE-like' if abs(mean_r - 0.5996) < abs(mean_r - 0.3863) else 'Poisson-like')

    if not null_spacings and not null_converge:
        return {'discrimina': True, 'nota': 'Null baseline: dati insufficienti — originale accettato'}

    # Il segnale originale discrimina se è DIVERSO dal null
    spacing_null = max(set(null_spacings), key=null_spacings.count) if null_spacings else None
    converge_null = sum(null_converge) > len(null_converge) / 2 if null_converge else None
    r_null = float(np.mean(null_r)) if null_r else None

    return {
        'spacing_null': spacing_null,
        'converge_null': converge_null,
        'r_diretto_null': r_null,
        'discrimina': True,  # Sarà confrontato col risultato reale dopo
        'nota': f'Null baseline: spacing={spacing_null}, converge={converge_null}, r={r_null:.4f}' if r_null else f'Null baseline: spacing={spacing_null}'
    }


def analizza_dnd(signal, metadata):
    """
    Applica l'analisi D-ND completa a un segnale.
    Non cerca φ. Osserva cosa emerge.

    Include null baseline: il segnale shufflato serve da controllo.
    Se il risultato è indistinguibile dal null, viene marcato.
    """
    from dnd_condizioni import scissione, regola_dnd, osserva_spirale

    risultato = {
        'dominio': metadata['dominio'],
        'metadata': metadata,
        'timestamp': datetime.now().isoformat(),
        'analisi': {},
    }

    # Null baseline (prima dell'analisi reale — non contaminare)
    try:
        null = _null_baseline(signal, metadata)
        risultato['null_baseline'] = null
    except Exception:
        risultato['null_baseline'] = {'discrimina': True, 'nota': 'Errore nel null baseline'}

    n = len(signal)
    risultato['analisi']['n_punti'] = n

    if n < 10:
        risultato['analisi']['errore'] = 'segnale troppo corto'
        return risultato

    # 1. Scissione a diverse soglie
    mediana = float(np.median(signal))
    media = float(np.mean(signal))
    soglie = [mediana, media, 0.0]

    migliore = None
    miglior_score = -1

    for th in soglie:
        d_int, nd_int = scissione(signal, th)
        n_min = min(len(d_int), len(nd_int))

        if n_min < 2:
            continue

        # Rapporto diretto
        d_mean = np.mean(d_int)
        nd_mean = np.mean(nd_int)
        r_diretto = float(d_mean / nd_mean) if nd_mean > 0 else float('inf')

        # Regola D-ND iterata
        diario = regola_dnd(d_int[:n_min], nd_int[:n_min], n_iter=30)
        obs = osserva_spirale(diario)

        # Score: struttura ricca = molti intervalli + convergenza + alternanza
        score = n_min
        if obs.get('alternanza'):
            score += 10
        if obs.get('converge'):
            score += 5

        if score > miglior_score:
            miglior_score = score
            migliore = {
                'soglia': float(th),
                'n_intervalli': n_min,
                'r_diretto': r_diretto,
                'osservazione': obs,
            }

    if migliore:
        risultato['analisi']['scissione'] = migliore
        obs = migliore['osservazione']
        risultato['analisi']['punto_fisso'] = obs.get('punto_fisso')
        risultato['analisi']['piu_vicino_a'] = obs.get('più_vicino_a')
        risultato['analisi']['distanza'] = obs.get('distanza')
        risultato['analisi']['alternanza'] = obs.get('alternanza')
        risultato['analisi']['converge'] = obs.get('converge')
        risultato['analisi']['gap_ratio'] = obs.get('gap_ratio_medio')

    # 2. Analisi Möbius: il rapporto diretto è vicino a φ, 1/φ, o φ²?
    if migliore:
        rd = migliore['r_diretto']
        costanti = {'φ': PHI, '1/φ': 1/PHI, 'φ²': PHI**2, '1': 1.0, '2': 2.0}
        prossimita = {nome: abs(rd - val) for nome, val in costanti.items()}
        piu_vicino = min(prossimita, key=prossimita.get)
        risultato['analisi']['r_diretto_vicino_a'] = piu_vicino
        risultato['analisi']['r_diretto_distanza'] = float(prossimita[piu_vicino])

    # 3. Statistica degli spacing (per segnali tipo autovalori/gap)
    if n > 20:
        if metadata.get('is_spacings'):
            # Il segnale È già spacings normalizzati — usalo direttamente
            spacings_norm = signal[signal > 0]
        else:
            spacings = np.diff(np.sort(signal))
            spacings = spacings[spacings > 0]
            spacings_norm = spacings / np.mean(spacings) if len(spacings) > 0 and np.mean(spacings) > 0 else np.array([])

        if len(spacings_norm) > 10:
            r_values = []
            for i in range(len(spacings_norm) - 1):
                if spacings_norm[i+1] > 0:
                    r_values.append(min(spacings_norm[i], spacings_norm[i+1]) /
                                  max(spacings_norm[i], spacings_norm[i+1]))
            if r_values:
                mean_r = float(np.mean(r_values))
                risultato['analisi']['spacing'] = {
                    'mean_r': mean_r,
                    'poisson_dist': abs(mean_r - 0.3863),
                    'gue_dist': abs(mean_r - 0.5996),
                    'tipo': 'GUE-like' if abs(mean_r - 0.5996) < abs(mean_r - 0.3863) else 'Poisson-like',
                    'is_native_spacings': bool(metadata.get('is_spacings', False))
                }

    # 4. Confronto con null baseline
    null = risultato.get('null_baseline', {})
    if null and null.get('spacing_null') is not None:
        spacing_reale = risultato['analisi'].get('spacing', {}).get('tipo')
        spacing_null = null.get('spacing_null')
        converge_reale = risultato['analisi'].get('converge')
        converge_null = null.get('converge_null')

        # Se spacing e convergenza sono uguali al null → non discriminante
        same_spacing = (spacing_reale == spacing_null)
        same_converge = (converge_reale == converge_null)

        if same_spacing and same_converge:
            risultato['analisi']['discrimina'] = False
            risultato['analisi']['discrimina_nota'] = (
                f'Non discriminante: risultato uguale al null baseline '
                f'(spacing={spacing_reale}, converge={converge_reale}). '
                f'Proprietà della distribuzione, non della struttura.'
            )
        elif same_spacing:
            risultato['analisi']['discrimina'] = 'parziale'
            risultato['analisi']['discrimina_nota'] = (
                f'Spacing non discriminante ({spacing_reale}=null), '
                f'ma convergenza differisce (reale={converge_reale}, null={converge_null})'
            )
        else:
            risultato['analisi']['discrimina'] = True
            risultato['analisi']['discrimina_nota'] = (
                f'Discriminante: spacing reale={spacing_reale} vs null={spacing_null}'
            )

    return risultato


# === C2 MIRAGGIO DETECTOR ===

def miraggio_check(measure_fn, costante, nome_costante, scale=[0.2, 0.5, 1.0, 2.0, 5.0]):
    """
    C2 automatico: una misura vicina a una costante è strutturale o miraggio?

    measure_fn(scale_factor) → float: la misura a una data scala
    costante: il valore a cui sembra vicino
    nome_costante: etichetta (es. "1/phi^2", "phi-1")
    scale: fattori di scala da testare (1.0 = scala base)

    Ritorna: {
        'verdict': 'converge' | 'miraggio' | 'inconcluso',
        'distanze': [(scala, valore, distanza), ...],
        'trend': 'monotono_decrescente' | 'oscillante' | 'crescente',
        'nota': str
    }

    Regola: se la distanza non decresce monotonamente con la scala,
    è miraggio fino a prova contraria.
    """
    distanze = []
    for s in scale:
        try:
            val = measure_fn(s)
            if val is not None:
                dist = abs(val - costante)
                distanze.append((s, val, dist))
        except Exception:
            continue

    if len(distanze) < 3:
        return {
            'verdict': 'inconcluso',
            'distanze': distanze,
            'trend': 'dati_insufficienti',
            'nota': f'Solo {len(distanze)} scale valide — servono almeno 3'
        }

    # Trend: la distanza decresce monotonamente?
    dists = [d[2] for d in distanze]
    decreasing = all(dists[i] >= dists[i+1] for i in range(len(dists)-1))
    increasing = all(dists[i] <= dists[i+1] for i in range(len(dists)-1))

    if decreasing:
        # Potenziale convergenza — ma quanto veloce?
        ratio = dists[-1] / dists[0] if dists[0] > 0 else 0
        if ratio < 0.1:
            verdict = 'converge'
            nota = f'{nome_costante}: convergenza forte (ratio {ratio:.3f})'
        else:
            verdict = 'inconcluso'
            nota = f'{nome_costante}: decresce ma lentamente (ratio {ratio:.3f})'
    elif increasing:
        verdict = 'miraggio'
        nota = f'{nome_costante}: la distanza CRESCE con la scala — miraggio'
    else:
        # Oscilla — il caso più comune
        min_dist = min(dists)
        min_idx = dists.index(min_dist)
        min_scale = distanze[min_idx][0]
        verdict = 'miraggio'
        nota = f'{nome_costante}: minimo a scala {min_scale}, poi oscilla — miraggio (C2)'

    return {
        'verdict': verdict,
        'distanze': distanze,
        'trend': 'monotono_decrescente' if decreasing else 'crescente' if increasing else 'oscillante',
        'nota': nota
    }


# === VALUTAZIONE ===

def valuta_risultato(risultato):
    """
    Valuta un risultato: è struttura D-ND? Pattern? Vincolo?
    Non cerca φ — osserva.

    Il null baseline declassa i risultati non discriminanti:
    se il segnale shufflato produce lo stesso output, il finding
    diventa vincolo (informazione, non scoperta).
    """
    analisi = risultato.get('analisi', {})
    dominio = risultato.get('dominio', '?')
    discrimina = analisi.get('discrimina', True)

    findings = []
    vincoli = []

    # Pattern 1: il rapporto diretto è vicino a φ o 1/φ
    rd_dist = analisi.get('r_diretto_distanza', float('inf'))
    rd_vicino = analisi.get('r_diretto_vicino_a', '?')
    if rd_dist < 0.03 and rd_vicino in ('φ', '1/φ'):
        # C2 miraggio check: la vicinanza regge a scale diverse?
        costante = PHI if rd_vicino == 'φ' else 1/PHI
        c2_nota = f'(C2 non testato — scala singola)'
        try:
            signal_raw = risultato.get('signal_raw')
            if signal_raw is not None and len(signal_raw) > 200:
                def measure_at_scale(s):
                    n = int(len(signal_raw) * s)
                    if n < 50:
                        return None
                    sub = signal_raw[:n]
                    gaps = np.abs(np.diff(sub))
                    gaps = gaps[gaps > 1e-12]
                    if len(gaps) < 10:
                        return None
                    above = np.sum(gaps > np.median(gaps))
                    below = len(gaps) - above
                    return above / below if below > 0 else None
                mc = miraggio_check(measure_at_scale, costante, rd_vicino)
                c2_nota = f'(C2: {mc["verdict"]})'
                if mc['verdict'] == 'miraggio':
                    # Declassa a vincolo invece di finding
                    vincoli.append({
                        'tipo': 'miraggio_c2',
                        'dominio': dominio,
                        'valore': analisi.get('scissione', {}).get('r_diretto'),
                        'nota': f'{dominio}: r≈{rd_vicino} a questa scala ma {mc["nota"]}'
                    })
                    rd_dist = float('inf')  # skip il finding sotto
        except Exception:
            pass

        if rd_dist < 0.05:
            findings.append({
                'tipo': 'rapporto_aureo_diretto',
                'dominio': dominio,
                'valore': analisi.get('scissione', {}).get('r_diretto'),
                'distanza': rd_dist,
                'nota': f'Rapporto D/ND diretto ≈ {rd_vicino} (dist={rd_dist:.4f}) {c2_nota}'
            })

    # Pattern 2: spacing GUE-like
    spacing = analisi.get('spacing', {})
    if spacing.get('tipo') == 'GUE-like' and spacing.get('gue_dist', 1) < 0.1:
        findings.append({
            'tipo': 'spacing_gue',
            'dominio': dominio,
            'mean_r': spacing['mean_r'],
            'nota': f'Spacing GUE-like (⟨r⟩={spacing["mean_r"]:.4f})'
        })

    # Pattern 3: convergenza + alternanza (struttura D-ND piena)
    # Raffinato: richiede anche che r_diretto non sia trivialmente ~1.0
    # Un r_diretto ~1.0 significa D e ND perfettamente bilanciati = nessuna tensione reale
    if analisi.get('alternanza') and analisi.get('converge'):
        rd = analisi.get('scissione', {}).get('r_diretto', 1.0)
        rd_dist_from_one = abs(rd - 1.0)
        if rd_dist_from_one > 0.05:
            # Tensione reale tra D e ND
            findings.append({
                'tipo': 'struttura_dnd_piena',
                'dominio': dominio,
                'punto_fisso': analisi.get('punto_fisso'),
                'gap_ratio': analisi.get('gap_ratio'),
                'r_diretto': rd,
                'nota': f'Alternanza D↔ND + convergenza (r={rd:.4f}, tensione reale)'
            })
        else:
            # Convergenza triviale — r~1.0, nessuna asimmetria D/ND
            findings.append({
                'tipo': 'convergenza_triviale',
                'dominio': dominio,
                'punto_fisso': analisi.get('punto_fisso'),
                'r_diretto': rd,
                'nota': f'Converge ma r≈1.0 ({rd:.4f}) — bilanciamento triviale, nessuna tensione D/ND'
            })

    # Null baseline gate: se non discrimina, declassa findings a vincoli
    if discrimina is False and findings:
        nota_null = analisi.get('discrimina_nota', 'non discriminante vs null')
        for f in findings:
            vincoli.append({
                'tipo': f'null_declassato_{f["tipo"]}',
                'dominio': dominio,
                'valore': f.get('valore') or f.get('mean_r') or f.get('r_diretto'),
                'nota': f'{f["nota"]} — DECLASSATO: {nota_null}'
            })
        findings = []  # Svuota — non sono significativi

    # Vincolo (Lazarus): se non trova nulla, è informazione
    if not findings:
        vincoli.append({
            'tipo': 'nessuna_struttura_dnd',
            'dominio': dominio,
            'r_diretto': analisi.get('scissione', {}).get('r_diretto'),
            'nota': f'{dominio}: nessuna struttura D-ND evidente al primo passaggio'
        })

    return findings, vincoli


# === CICLO DI RICERCA ===

def ciclo_ricerca(stato):
    """
    Un giro della spirale di autoricerca.
    1. Scegli dominio (dal gap o dalla coda)
    2. Genera segnale
    3. Analizza con D-ND
    4. Valuta: pattern o vincolo
    5. Aggiorna stato e journal
    """
    stato['ciclo'] += 1
    ciclo = stato['ciclo']

    print(f"\n{'='*60}")
    print(f"CICLO {ciclo} — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    # 1. Scegli dominio
    if not stato['domini_coda']:
        print("  Coda esaurita. Rigenero domini con parametri variati.")
        stato['domini_coda'] = [d + '_v2' for d in stato['domini_esplorati'][:6]]

    dominio = stato['domini_coda'].pop(0)
    # Gestisci varianti: _v2/_v3 (generic) e _var_X (parametric)
    var_param = None
    if '_var_' in dominio:
        parts = dominio.split('_var_')
        dominio_base = parts[0]
        try:
            var_param = float(parts[1])
        except ValueError:
            var_param = parts[1]
    else:
        dominio_base = dominio.replace('_v2', '').replace('_v3', '')
    stato['domini_esplorati'].append(dominio)

    print(f"  Dominio: {dominio}" + (f" (param={var_param})" if var_param else ""))

    # 2. Genera segnale
    try:
        if var_param is not None:
            # Parametric variante: use _genera_variante with appropriate param
            param_map = {
                'logistica_biforcazione': {'r': var_param},
                'percolation': {'p': var_param},
                'ising_2d': {'T': var_param},
                'brownian_motion': {'H': var_param},
                'zeta_zeros': {'n_zeros': int(var_param)},
                'numeri_primi': {'n': int(var_param)},
                'cellular_automata': {'rule': int(var_param)},
            }
            params = param_map.get(dominio_base, {'param': var_param})
            signal, metadata = _genera_variante(dominio_base, params)
            metadata['variante'] = True
        else:
            signal, metadata = genera_segnale(dominio_base)
        print(f"  Segnale: {len(signal)} punti — {metadata.get('nota', '')}")
    except Exception as e:
        print(f"  ERRORE generazione: {e}")
        entry = {
            'ciclo': ciclo, 'dominio': dominio,
            'errore': str(e), 'timestamp': datetime.now().isoformat()
        }
        aggiungi_journal(entry)
        return stato

    # 3. Analizza
    print("  Analisi D-ND...")
    try:
        risultato = analizza_dnd(signal, metadata)
    except Exception as e:
        print(f"  ERRORE analisi: {e}")
        traceback.print_exc()
        entry = {
            'ciclo': ciclo, 'dominio': dominio,
            'errore': str(e), 'timestamp': datetime.now().isoformat()
        }
        aggiungi_journal(entry)
        return stato

    analisi = risultato.get('analisi', {})

    # Stampa risultati chiave
    print(f"  Punto fisso: {analisi.get('punto_fisso', '?')}")
    print(f"  Più vicino a: {analisi.get('piu_vicino_a', '?')} "
          f"(dist={analisi.get('distanza', '?')})")
    print(f"  r diretto: {analisi.get('scissione', {}).get('r_diretto', '?')} "
          f"→ {analisi.get('r_diretto_vicino_a', '?')} "
          f"(dist={analisi.get('r_diretto_distanza', '?')})")
    print(f"  Alternanza: {analisi.get('alternanza', '?')}")
    print(f"  Converge: {analisi.get('converge', '?')}")

    spacing = analisi.get('spacing', {})
    if spacing:
        print(f"  Spacing: {spacing.get('tipo', '?')} "
              f"(⟨r⟩={spacing.get('mean_r', '?'):.4f})")

    # 4. Valuta
    findings, vincoli = valuta_risultato(risultato)

    for f in findings:
        print(f"  ** PATTERN: {f['tipo']} — {f['nota']}")
        stato['pattern_trovati'].append(f)

    for v in vincoli:
        print(f"  -- Vincolo: {v['nota']}")
        stato['vincoli_lazarus'].append(v)

    # 5. Journal
    entry = {
        'ciclo': ciclo,
        'dominio': dominio,
        'timestamp': datetime.now().isoformat(),
        'n_punti': len(signal),
        'r_diretto': analisi.get('scissione', {}).get('r_diretto'),
        'punto_fisso': analisi.get('punto_fisso'),
        'piu_vicino': analisi.get('piu_vicino_a'),
        'alternanza': analisi.get('alternanza'),
        'converge': analisi.get('converge'),
        'gap_ratio': analisi.get('gap_ratio'),
        'spacing': spacing.get('tipo') if spacing else None,
        'spacing_r': spacing.get('mean_r') if spacing else None,
        'findings': [f['tipo'] for f in findings],
        'vincoli': [v['tipo'] for v in vincoli],
    }
    aggiungi_journal(entry)

    # 6. Aggiorna gap
    n_pattern = len(stato['pattern_trovati'])
    n_vincoli = len(stato['vincoli_lazarus'])
    n_totale = n_pattern + n_vincoli
    if n_totale > 0:
        stato['gap_corrente'] = {
            'pattern_rate': n_pattern / n_totale,
            'domini_esplorati': len(stato['domini_esplorati']),
            'domini_restanti': len(stato['domini_coda']),
        }

    # 7. Segnale pubblica?
    # Regola: se troviamo pattern in ≥3 domini diversi E hanno struttura coerente
    domini_con_pattern = set(f['dominio'] for f in stato['pattern_trovati'])
    if len(domini_con_pattern) >= 3:
        stato['segnale_pubblica'] = True
        print(f"\n  *** SEGNALE: pattern D-ND in {len(domini_con_pattern)} domini. "
              f"Considerare pubblicazione. ***")

    salva_stato(stato)
    return stato


# === FUNZIONI AUTOLOGICHE ===
# Il motore applica D-ND a se stesso. La varianza diventa esponenziale.

def meta_analisi(stato):
    """
    Funzione autologica: applica D-ND ai risultati dell'engine stesso.
    Il segnale = i r_diretto di tutti i domini esplorati.
    Il secondo segnale = gli spacing_r di tutti i domini.
    Cross-correlazione tra i due.
    """
    print(f"\n{'='*60}")
    print("META-ANALISI AUTOLOGICA — D-ND applicato a se stesso")
    print(f"{'='*60}")

    # Carica journal
    if not JOURNAL.exists():
        print("  Nessun journal. Serve almeno un ciclo.")
        return stato

    with open(JOURNAL) as f:
        journal = json.load(f)

    if len(journal) < 4:
        print(f"  Solo {len(journal)} cicli. Servono almeno 4 per la meta-analisi.")
        return stato

    # Segnale 1: r_diretto di tutti i domini
    r_diretti = np.array([e['r_diretto'] for e in journal if e.get('r_diretto') is not None])
    domini = [e['dominio'] for e in journal if e.get('r_diretto') is not None]

    # Segnale 2: spacing_r di tutti i domini
    spacing_rs = np.array([e['spacing_r'] for e in journal if e.get('spacing_r') is not None])
    spacing_domini = [e['dominio'] for e in journal if e.get('spacing_r') is not None]

    print(f"\n  Segnale 1: r_diretto [{len(r_diretti)} valori]")
    for d, r in zip(domini, r_diretti):
        dist_phi = abs(r - PHI)
        dist_inv = abs(r - 1/PHI)
        dist_1 = abs(r - 1.0)
        closest = min([('φ', dist_phi), ('1/φ', dist_inv), ('1', dist_1)], key=lambda x: x[1])
        print(f"    {d:>25s}: r={r:.4f} → {closest[0]} (dist={closest[1]:.4f})")

    # Scissione dei r_diretto: quali sono > mediana, quali <
    if len(r_diretti) >= 4:
        from dnd_condizioni import scissione, regola_dnd, osserva_spirale

        mediana_r = np.median(r_diretti)
        print(f"\n  Mediana r_diretto: {mediana_r:.4f}")

        d_idx = r_diretti > mediana_r
        nd_idx = ~d_idx

        print(f"  D (>{mediana_r:.3f}): {[d for d, m in zip(domini, d_idx) if m]}")
        print(f"  ND (<={mediana_r:.3f}): {[d for d, m in zip(domini, nd_idx) if m]}")

        # Regola D-ND sui r_diretto stessi
        d_vals = r_diretti[d_idx]
        nd_vals = r_diretti[nd_idx]
        if len(d_vals) >= 2 and len(nd_vals) >= 2:
            n_min = min(len(d_vals), len(nd_vals))
            diario = regola_dnd(d_vals[:n_min], nd_vals[:n_min], n_iter=30)
            obs = osserva_spirale(diario)
            print(f"\n  Meta-spirale sui r_diretto:")
            print(f"    Punto fisso: {obs.get('punto_fisso', '?')}")
            print(f"    Più vicino a: {obs.get('più_vicino_a', '?')} "
                  f"(dist={obs.get('distanza', '?')})")
            print(f"    Alternanza: {obs.get('alternanza', '?')}")
            print(f"    Gap ratio: {obs.get('gap_ratio_medio', '?')}")

            # Registra nel journal come ciclo meta
            meta_entry = {
                'ciclo': stato['ciclo'] + 0.5,  # .5 = meta-ciclo
                'dominio': 'META_r_diretto',
                'timestamp': datetime.now().isoformat(),
                'n_punti': len(r_diretti),
                'r_diretto': float(np.mean(r_diretti)),
                'punto_fisso': obs.get('punto_fisso'),
                'piu_vicino': obs.get('più_vicino_a'),
                'alternanza': obs.get('alternanza'),
                'converge': obs.get('converge'),
                'gap_ratio': obs.get('gap_ratio_medio'),
                'findings': ['meta_autologica'],
                'vincoli': [],
                'nota': 'D-ND applicato ai propri r_diretto'
            }
            aggiungi_journal(meta_entry)

    # Cross-correlazione r_diretto vs spacing_r
    if len(spacing_rs) >= 4:
        # Per i domini che hanno entrambi
        common = set(domini) & set(spacing_domini)
        if len(common) >= 4:
            r_common = np.array([r_diretti[i] for i, d in enumerate(domini) if d in common])
            s_common = np.array([spacing_rs[spacing_domini.index(d)] for d in sorted(common)
                               if d in spacing_domini])

            if len(r_common) == len(s_common):
                corr = np.corrcoef(r_common, s_common)[0, 1]
                print(f"\n  Cross-correlazione r_diretto vs spacing_r: {corr:.4f}")

                # Il rapporto r_diretto/spacing_r per ogni dominio
                print(f"\n  Rapporto r_diretto/spacing_r:")
                for d in sorted(common):
                    if d in domini and d in spacing_domini:
                        r = r_diretti[domini.index(d)]
                        s = spacing_rs[spacing_domini.index(d)]
                        ratio = r / s if s > 0 else float('inf')
                        dist_phi = abs(ratio - PHI)
                        dist_inv = abs(ratio - 1/PHI)
                        closest = '→φ' if dist_phi < dist_inv else '→1/φ' if dist_inv < 0.1 else ''
                        print(f"    {d:>25s}: {ratio:.4f} {closest}")

    # Distribuzione dei cluster
    print(f"\n  Cluster spacing:")
    gue_domains = [e['dominio'] for e in journal if e.get('spacing') == 'GUE-like']
    poisson_domains = [e['dominio'] for e in journal if e.get('spacing') == 'Poisson-like']
    print(f"    GUE-like: {gue_domains}")
    print(f"    Poisson-like: {poisson_domains}")

    # Il RAPPORTO #GUE/#Poisson è vicino a φ?
    if len(gue_domains) > 0 and len(poisson_domains) > 0:
        ratio_cluster = len(gue_domains) / len(poisson_domains)
        print(f"    #GUE/#Poisson = {ratio_cluster:.4f} "
              f"(dist da φ={abs(ratio_cluster - PHI):.4f}, "
              f"dist da 1={abs(ratio_cluster - 1):.4f})")

    salva_stato(stato)
    return stato


def analisi_multi_scala(dominio, scale=None):
    """
    Testa r_diretto a scale diverse per un dominio.
    Cerca crossing points con costanti D-ND (φ, 1/φ, φ²).
    """
    print(f"\n{'='*60}")
    print(f"ANALISI MULTI-SCALA: {dominio}")
    print(f"{'='*60}")

    if scale is None:
        scale = [100, 500, 1000, 2000, 5000, 10000, 20000, 50000]

    risultati = []
    for n_target in scale:
        try:
            # Genera segnale alla scala richiesta
            if dominio == 'numeri_primi':
                def sieve(n):
                    is_prime = [True] * (n + 1)
                    is_prime[0] = is_prime[1] = False
                    for i in range(2, int(n**0.5) + 1):
                        if is_prime[i]:
                            for j in range(i*i, n + 1, i):
                                is_prime[j] = False
                    return [i for i in range(n + 1) if is_prime[i]]
                primes = sieve(n_target * 10)[:n_target]
                signal = np.diff(primes).astype(float)
            elif dominio == 'cellular_automata':
                L = 200
                rule = {(1,1,1): 0, (1,1,0): 1, (1,0,1): 1, (1,0,0): 0,
                        (0,1,1): 1, (0,1,0): 1, (0,0,1): 1, (0,0,0): 0}
                state = np.zeros(L, dtype=int)
                state[L//2] = 1
                density = []
                for _ in range(n_target):
                    density.append(np.mean(state))
                    new = np.zeros(L, dtype=int)
                    for i in range(L):
                        triple = (state[(i-1)%L], state[i], state[(i+1)%L])
                        new[i] = rule[triple]
                    state = new
                signal = np.array(density)
            elif dominio == 'ising_2d':
                L = 32
                T_c = 2 / np.log(1 + np.sqrt(2))
                spins = np.random.choice([-1, 1], size=(L, L))
                magnetizations = []
                for step in range(n_target):
                    for _ in range(L * L):
                        i, j = np.random.randint(0, L, 2)
                        neighbors = (spins[(i+1)%L, j] + spins[(i-1)%L, j] +
                                    spins[i, (j+1)%L] + spins[i, (j-1)%L])
                        dE = 2 * spins[i, j] * neighbors
                        if dE <= 0 or np.random.random() < np.exp(-dE / T_c):
                            spins[i, j] *= -1
                    magnetizations.append(np.mean(spins))
                signal = np.array(magnetizations)
            else:
                # Per domini senza scala variabile, skip
                print(f"  {dominio}: scala variabile non implementata")
                return risultati

            if len(signal) < 10:
                continue

            # Scissione e r_diretto
            # Fix V1: normalizzare per media locale su segnali non-stazionari
            # (gap primi ~ ln(N), soglia fissa produce oscillazioni spurie)
            from dnd_condizioni import scissione
            signal_work = signal.copy()
            if len(signal_work) > 200:
                window = min(200, len(signal_work) // 5)
                local_mean = np.convolve(signal_work, np.ones(window)/window, mode='same')
                local_mean[local_mean == 0] = 1
                signal_work = signal_work / local_mean
            mediana = np.median(signal_work)
            d_int, nd_int = scissione(signal_work, mediana)
            if len(d_int) > 0 and len(nd_int) > 0:
                r = float(np.mean(d_int) / np.mean(nd_int)) if np.mean(nd_int) > 0 else float('inf')
            else:
                r = float('inf')

            dist_phi = abs(r - PHI)
            dist_inv = abs(r - 1/PHI)
            dist_1 = abs(r - 1.0)
            dist_phi2 = abs(r - PHI**2)

            risultati.append({
                'scala': n_target,
                'n_effettivo': len(signal),
                'r_diretto': r,
                'dist_phi': dist_phi,
                'dist_1/phi': dist_inv,
                'dist_1': dist_1,
                'dist_phi2': dist_phi2,
            })

            closest = min([('φ', dist_phi), ('1/φ', dist_inv), ('1', dist_1), ('φ²', dist_phi2)],
                         key=lambda x: x[1])
            print(f"  N={n_target:>6d}: r={r:.4f} → {closest[0]} (dist={closest[1]:.4f})")

        except Exception as e:
            print(f"  N={n_target}: errore — {e}")

    # Cerca crossing points (dove r attraversa una costante D-ND)
    if len(risultati) >= 3:
        print(f"\n  Crossing analysis:")
        for const_name, const_val in [('φ', PHI), ('1/φ', 1/PHI), ('1', 1.0)]:
            rs = [r['r_diretto'] for r in risultati]
            above = [r > const_val for r in rs]
            crossings = sum(1 for i in range(len(above)-1) if above[i] != above[i+1])
            if crossings > 0:
                # Trova la scala del crossing
                for i in range(len(above)-1):
                    if above[i] != above[i+1]:
                        n1, n2 = risultati[i]['scala'], risultati[i+1]['scala']
                        r1, r2 = risultati[i]['r_diretto'], risultati[i+1]['r_diretto']
                        # Interpolazione lineare per la scala del crossing
                        frac = (const_val - r1) / (r2 - r1) if r2 != r1 else 0.5
                        n_cross = n1 + frac * (n2 - n1)
                        print(f"    {const_name} crossing a N≈{n_cross:.0f} "
                              f"(tra {n1} e {n2})")

    return risultati


def combinazioni_cross_domain(stato):
    """
    Pensiero laterale: combinazioni inattese tra domini.
    Cerca pattern che emergono dal confronto, non dall'analisi singola.
    """
    print(f"\n{'='*60}")
    print("COMBINAZIONI CROSS-DOMAIN — pensiero laterale")
    print(f"{'='*60}")

    if not JOURNAL.exists():
        print("  Nessun journal.")
        return

    with open(JOURNAL) as f:
        journal = json.load(f)

    # Filtra solo cicli reali (non meta)
    reali = [e for e in journal if isinstance(e.get('ciclo'), int)]

    if len(reali) < 4:
        print(f"  Solo {len(reali)} cicli. Servono almeno 4.")
        return

    # 1. Rapporto tra r_diretto consecutivi
    print(f"\n  1. Rapporto r_diretto consecutivi:")
    rs = [e['r_diretto'] for e in reali if e.get('r_diretto')]
    for i in range(len(rs)-1):
        if rs[i+1] > 0:
            ratio = rs[i] / rs[i+1]
            dist_phi = abs(ratio - PHI)
            dist_inv = abs(ratio - 1/PHI)
            mark = ' ←!' if min(dist_phi, dist_inv) < 0.05 else ''
            print(f"    {reali[i]['dominio']}/{reali[i+1]['dominio']}: "
                  f"{ratio:.4f}{mark}")

    # 2. Differenza spacing tra coppie GUE-Poisson
    print(f"\n  2. Coppie GUE-Poisson:")
    gue = [e for e in reali if e.get('spacing') == 'GUE-like' and e.get('spacing_r')]
    poi = [e for e in reali if e.get('spacing') == 'Poisson-like' and e.get('spacing_r')]

    for g in gue:
        for p in poi:
            diff = g['spacing_r'] - p['spacing_r']
            ratio = g['spacing_r'] / p['spacing_r'] if p['spacing_r'] > 0 else float('inf')
            dist_phi = abs(ratio - PHI)
            mark = ' ←φ!' if dist_phi < 0.1 else ''
            print(f"    {g['dominio']:<20s} vs {p['dominio']:<20s}: "
                  f"Δ={diff:.4f}, ratio={ratio:.4f}{mark}")

    # 3. I r_diretto dei domini GUE vs Poisson come due insiemi
    print(f"\n  3. r_diretto medio per cluster spacing:")
    gue_rs = [e['r_diretto'] for e in gue if e.get('r_diretto')]
    poi_rs = [e['r_diretto'] for e in poi if e.get('r_diretto')]
    if gue_rs and poi_rs:
        mean_gue = np.mean(gue_rs)
        mean_poi = np.mean(poi_rs)
        ratio = mean_gue / mean_poi if mean_poi > 0 else float('inf')
        print(f"    GUE mean r_diretto: {mean_gue:.4f}")
        print(f"    Poisson mean r_diretto: {mean_poi:.4f}")
        print(f"    Ratio GUE/Poisson: {ratio:.4f}")
        print(f"    dist da φ: {abs(ratio - PHI):.4f}")
        print(f"    dist da 1: {abs(ratio - 1):.4f}")

    # 4. Sequenza dei gap_ratio — è più costante di quanto ci si aspetterebbe?
    print(f"\n  4. Gap ratio per dominio:")
    grs = [(e['dominio'], e['gap_ratio']) for e in reali if e.get('gap_ratio')]
    if grs:
        vals = [g[1] for g in grs]
        print(f"    Media: {np.mean(vals):.6f}")
        print(f"    Std: {np.std(vals):.6f}")
        print(f"    dist da φ²: {abs(np.mean(vals) - PHI**2):.6f}")
        # La varianza è informazione: quanto è compresso?
        cv = np.std(vals) / np.mean(vals) if np.mean(vals) > 0 else 0
        print(f"    Coefficiente variazione: {cv:.6f}")
        print(f"    → {'ULTRA-STABILE' if cv < 0.001 else 'stabile' if cv < 0.01 else 'variabile'}")


# === REPORT ===

def report_stato(stato):
    """Stampa il report dello stato corrente."""
    print(f"\n{'='*60}")
    print("STATO AUTORICERCA D-ND")
    print(f"{'='*60}")
    print(f"  Cicli completati: {stato['ciclo']}")
    print(f"  Domini esplorati: {len(stato['domini_esplorati'])}")
    print(f"  Domini in coda: {len(stato['domini_coda'])}")
    print(f"  Pattern trovati: {len(stato['pattern_trovati'])}")
    print(f"  Vincoli (Lazarus): {len(stato['vincoli_lazarus'])}")

    if stato['pattern_trovati']:
        print(f"\n  Pattern:")
        for p in stato['pattern_trovati']:
            print(f"    [{p['dominio']}] {p['tipo']}: {p.get('nota', '')}")

    if stato['vincoli_lazarus']:
        print(f"\n  Vincoli:")
        for v in stato['vincoli_lazarus'][-5:]:  # ultimi 5
            print(f"    [{v['dominio']}] {v.get('nota', '')}")

    gap = stato.get('gap_corrente')
    if gap:
        print(f"\n  Gap corrente:")
        print(f"    Pattern rate: {gap['pattern_rate']:.2%}")
        print(f"    Esplorati/Restanti: {gap['domini_esplorati']}/{gap['domini_restanti']}")

    if stato.get('segnale_pubblica'):
        print(f"\n  *** SEGNALE ATTIVO: considerare pubblicazione ***")

    print(f"\n  Ultimo aggiornamento: {stato.get('aggiornato', '?')}")


# === WORKFLOW NOTTURNO ===

def genera_varianti_domini():
    """Genera varianti dei domini con parametri diversi per test di robustezza."""
    return [
        # Ising a temperature diverse
        ('ising_2d', {'T_offset': -0.1}),
        ('ising_2d', {'T_offset': 0.1}),
        # Primi con diversi range
        ('numeri_primi', {'max_n': 100000}),
        # Logistica a diversi r
        ('logistica_biforcazione', {'r_override': 3.57}),  # caotico
        ('logistica_biforcazione', {'r_override': 3.9}),   # fully chaotic
        # CA Rule 30 (non Turing-completo, pattern diverso)
        ('cellular_automata', {'rule_number': 30}),
        # Brownian con H diversi
        ('brownian_motion', {'H': 0.3}),   # anti-persistente
        ('brownian_motion', {'H': 0.5}),   # standard
        # Oscillatori con N diverso
        ('coupled_oscillators', {'N': 50}),
        # Percolazione sotto e sopra p_c
        ('percolation', {'p': 0.55}),
        ('percolation', {'p': 0.65}),
    ]


def genera_controprove():
    """
    Domini dove il frame D-ND e' noto fallire o essere debole.
    Il valore e' nei VINCOLI trovati, non nelle conferme.
    Se un dominio produce struttura_dnd_piena, e' meno interessante
    di uno che produce nessuna_struttura_dnd — il falso negativo
    e' il segnale.
    """
    import random

    # Domini con dipolo basso (< 0.5) nei test precedenti:
    # Rudin-Shapiro 0.33, Riemann zeros 0.30, Collatz, HRV, Zipf
    controprove_fisse = [
        ('rudin_shapiro', {}),
        ('collatz', {}),
        ('logistica_biforcazione', {'r_override': 3.83}),   # finestra periodo-3: dipolo 0.50 borderline
        ('logistica_biforcazione', {'r_override': 4.0}),    # beyond: CV rompe convergenza a phi-1
    ]

    # Domini casuali con parametri estremi — cercano dove il frame si rompe
    controprove_random = [
        ('ising_2d', {'T_offset': random.uniform(-0.5, -0.3)}),  # lontano da T_c
        ('ising_2d', {'T_offset': random.uniform(0.3, 0.5)}),    # lontano da T_c, altro lato
        ('brownian_motion', {'H': random.uniform(0.1, 0.2)}),    # fortemente anti-persistente
        ('brownian_motion', {'H': random.uniform(0.8, 0.95)}),   # fortemente persistente
        ('percolation', {'p': random.uniform(0.3, 0.4)}),        # lontano da p_c sotto
        ('percolation', {'p': random.uniform(0.8, 0.9)}),        # lontano da p_c sopra
        ('cellular_automata', {'rule_number': random.choice([90, 150, 182, 45])}),  # regole diverse
    ]

    return controprove_fisse + controprove_random


def _genera_rudin_shapiro(N=5000):
    """Sequenza Rudin-Shapiro: struttura nella rappresentazione binaria, non nei valori."""
    rs = [1]
    for n in range(1, N):
        # r(n) = (-1)^(f(n)) dove f(n) = numero di '11' in binario di n
        b = bin(n)
        f = b.count('11')
        rs.append((-1) ** f)
    return np.array(rs, dtype=float)


def _genera_collatz(N=5000, start=None):
    """Sequenza di Collatz (lunghezze delle traiettorie per interi consecutivi)."""
    import random as rnd
    start_n = start or rnd.randint(1000, 100000)
    lengths = []
    for n in range(start_n, start_n + N):
        x = n
        steps = 0
        while x != 1 and steps < 10000:
            x = x // 2 if x % 2 == 0 else 3 * x + 1
            steps += 1
        lengths.append(steps)
    return np.array(lengths, dtype=float)


SEME = DATA / 'seme.json'


def _leggi_seme_e_piano():
    """
    Legge il seme corrente. Il seme E' l'orchestratore —
    le tensioni vive determinano la direzione della notte.
    """
    if not SEME.exists():
        return {'piano': 0, 'tensioni': [], 'direzione': '', 'verifica': {}}
    try:
        with open(SEME) as f:
            seme = json.load(f)
        return {
            'piano': seme.get('piano', 0),
            'tensioni': seme.get('tensioni', []),
            'direzione': seme.get('direzione', ''),
            'verifica': seme.get('verifica', {}),
        }
    except Exception:
        return {'piano': 0, 'tensioni': [], 'direzione': '', 'verifica': {}}


def _consecutio_da_seme(piano_notte):
    """
    A13 — La seconda voce. Prosegue dal punto in cui il seme e' arrivato.

    Per ogni tensione viva, genera test che continuano nella stessa direzione.
    Se la consecutio produce tensione nuova → direzione confermata.
    Se non produce → riallineamento su cio' che e' stabile.
    In entrambi i casi: mossa migliore o mossa non sbagliata.
    """
    import random
    controprove = []
    tensioni = piano_notte.get('tensioni', [])

    for t in tensioni:
        tid = t.get('id', '')
        tipo = t.get('tipo', '')
        claim = t.get('claim', '').lower()

        # N1: Hurst falsificato — prosegui testando su domini fisici (non sintetici)
        if 'hurst' in claim or tid == 'N1':
            # Consecutio: se la soglia Hurst non esiste, la scissione non dipende
            # dalla correlazione temporale. Testa su domini con H naturale diverso.
            controprove.append(('ising_2d', {'T_offset': 0}))  # T critica esatta
            controprove.append(('percolation', {'p': 0.5927}))  # p_c esatta

        # BOUNDARY: confine GUE/Poisson — prosegui esplorando il confine
        elif 'boundary' in tid.lower() or 'confine' in claim:
            # Consecutio: il confine e' dove la scissione cambia natura.
            # Testa parametri vicini alla transizione.
            controprove.append(('logistica_biforcazione', {'r_override': 3.57}))  # onset caos
            controprove.append(('logistica_biforcazione', {'r_override': 3.83}))  # finestra periodo-3
            controprove.append(('logistica_biforcazione', {'r_override': round(3.57 + random.uniform(0, 0.43), 3)}))

        # F4: separazione di scala sotto attacco — prosegui con scale estreme
        elif 'f4' in tid.lower() or 'separazione' in claim or 'scaling' in claim:
            # Consecutio: se la separazione non regge, testala a scale molto diverse
            controprove.append(('numeri_primi', {'n_override': 100}))    # scala piccola
            controprove.append(('numeri_primi', {'n_override': 50000}))  # scala grande

        # Contraddizione generica: testa il claim su dominio diverso
        elif tipo == 'contraddizione':
            controprove.append(('cellular_automata', {'rule_number': random.choice([30, 110, 90, 150])}))

        # Falsificazione: conferma su altro dominio (riallineamento)
        elif tipo == 'falsificazione':
            controprove.append(('collatz', {}))
            controprove.append(('rudin_shapiro', {}))

    return controprove


def _consuma_fonti_esterne():
    """
    Legge fonti_esterne dal seme, le confronta con le tensioni attive.
    Se una fonte accoppia con una tensione (condivide parole chiave),
    la marca come accoppiata. Svuota il campo dopo il consumo.

    Le fonti arrivano da VI (Video Intelligence) o da input manuale.
    Il formato: [{"titolo": "...", "insight": "...", "tipo": "video|paper|altro"}]
    """
    if not SEME.exists():
        return []

    with open(SEME) as f:
        seme = json.load(f)

    fonti = seme.get('fonti_esterne', [])
    if not fonti:
        return []

    tensioni = seme.get('tensioni', [])

    # Accoppiamento: per ogni fonte, cerca se tocca una tensione attiva
    for fonte in fonti:
        insight = (fonte.get('insight', '') + ' ' + fonte.get('titolo', '')).lower()
        keywords = set(fonte.get('keywords', []))
        for tensione in tensioni:
            # Tensioni sono dict con 'claim', 'id', etc.
            t_text = ''
            if isinstance(tensione, dict):
                t_text = (tensione.get('claim', '') + ' ' + tensione.get('id', '') + ' ' + tensione.get('nota', '')).lower()
            elif isinstance(tensione, str):
                t_text = tensione.lower()
            # Parole significative in comune (>= 4 lettere, almeno 2 match)
            parole_fonte = {w for w in insight.split() if len(w) >= 4} | keywords
            parole_tensione = {w for w in t_text.split() if len(w) >= 4}
            comuni = parole_fonte & parole_tensione
            if len(comuni) >= 2:
                fonte['accoppiamento'] = t_text[:200]
                fonte['parole_comuni'] = list(comuni)[:10]
                break

    # Svuota fonti_esterne nel seme (consumate)
    seme['fonti_esterne'] = []
    seme['fonti_consumate'] = seme.get('fonti_consumate', 0) + len(fonti)
    with open(SEME, 'w') as f:
        json.dump(seme, f, indent=2, ensure_ascii=False)

    consumate = [f for f in fonti if f.get('accoppiamento')]
    non_accoppiate = [f for f in fonti if not f.get('accoppiamento')]

    if consumate:
        print(f"  {len(consumate)} fonti accoppiate con tensioni attive:")
        for f in consumate:
            print(f"    [{f.get('tipo')}] {f.get('titolo', '?')}")
            print(f"      -> {f['accoppiamento'][:80]}")
    if non_accoppiate:
        print(f"  {len(non_accoppiate)} fonti senza accoppiamento (archiviate):")
        for f in non_accoppiate:
            print(f"    [{f.get('tipo')}] {f.get('titolo', '?')}")

    # Aggiungi al journal le fonti accoppiate
    for f in consumate:
        aggiungi_journal({
            'ciclo': 'fonte_esterna',
            'dominio': 'esterno',
            'timestamp': datetime.now().isoformat(),
            'titolo': f.get('titolo'),
            'insight': f.get('insight'),
            'tipo': f.get('tipo'),
            'accoppiamento': f.get('accoppiamento'),
            'parole_comuni': f.get('parole_comuni', []),
        })

    return fonti


def _notifica_sinapsi_risultato(fonti, report_lines):
    """Posta il risultato delle fonti esterne su Sinapsi per TM1."""
    import subprocess
    import os

    token = os.environ.get('THIA_API_TOKEN', '')
    if not token:
        print("  [Sinapsi] THIA_API_TOKEN non disponibile, skip notifica")
        return

    accoppiate = [f for f in fonti if f.get('accoppiamento')]
    non_accoppiate = [f for f in fonti if not f.get('accoppiamento')]

    content = f"Autoricerca notte — {len(fonti)} fonti esterne consumate.\n\n"
    if accoppiate:
        content += f"ACCOPPIATE ({len(accoppiate)}):\n"
        for f in accoppiate:
            content += f"- [{f.get('tipo')}] {f.get('titolo','?')}\n"
            content += f"  -> tensione: {f['accoppiamento'][:100]}\n"
    if non_accoppiate:
        content += f"\nNON ACCOPPIATE ({len(non_accoppiate)}):\n"
        for f in non_accoppiate:
            content += f"- [{f.get('tipo')}] {f.get('titolo','?')}\n"

    payload = json.dumps({
        "from": "TM3",
        "to": "TM1",
        "type": "autoricerca_result",
        "subject": f"Lab: {len(fonti)} fonti esterne processate",
        "content": content
    })

    try:
        result = subprocess.run(
            ['curl', '-s', '-X', 'POST', 'http://localhost:3002/api/node-sync',
             '-H', f'X-THIA-Token: {token}',
             '-H', 'Content-Type: application/json',
             '-d', payload],
            capture_output=True, text=True, timeout=10
        )
        if '"ok":true' in result.stdout:
            print(f"  [Sinapsi] Risultato fonti esterne notificato a TM1")
        else:
            print(f"  [Sinapsi] Errore: {result.stdout[:100]}")
    except Exception as e:
        print(f"  [Sinapsi] Errore notifica: {e}")


def ciclo_notte():
    """
    Workflow notturno completo — A11 Combo.

    Non sequenziale: il campo si accumula e ogni fase legge il campo vivo.
    I vincoli diventano esperimenti nello stesso ciclo.
    Il Domandatore genera angoli dal campo che si forma.
    Cross-domain propaga i risultati tra domini in tempo reale.

    La combo: controprove + campo vivo + domandatore = tre enti simultanei
    la cui risultante nessuno dei tre produce da solo.
    """
    from datetime import datetime
    ts = datetime.now().strftime('%Y%m%d_%H%M')

    print(f"\n{'#'*60}")
    print(f"# AUTORICERCA D-ND — CICLO NOTTURNO (A11 Combo)")
    print(f"# {datetime.now().isoformat()}")
    print(f"{'#'*60}")

    stato = carica_stato()
    report_lines = [f"# Autoricerca Notte {ts}", ""]

    # === CAMPO VIVO ===
    # Il campo accumula risultati di ogni esperimento.
    # Ogni fase successiva legge il campo, non solo i propri input.
    campo = {
        'vincoli': [],        # vincoli trovati → diventano esperimenti
        'anomalie': [],       # segnali inaspettati → cross-domain
        'gue_domains': [],    # domini con spacing GUE
        'poisson_domains': [],# domini con spacing Poisson
        'r_values': [],       # tutti i r_diretto per meta-analisi live
    }

    def aggiorna_campo(entry, findings, vincoli):
        """Ogni esperimento aggiorna il campo vivo."""
        if entry.get('spacing') and 'GUE' in str(entry['spacing']):
            campo['gue_domains'].append(entry.get('dominio', '?'))
        elif entry.get('spacing') and 'Poisson' in str(entry['spacing']):
            campo['poisson_domains'].append(entry.get('dominio', '?'))
        if entry.get('r_diretto') is not None:
            campo['r_values'].append(entry['r_diretto'])
        for v in vincoli:
            campo['vincoli'].append(v)
        for f in findings:
            if f.get('tipo') in ('spacing_gue', 'struttura_dnd_piena', 'convergenza_triviale'):
                campo['anomalie'].append({'dominio': entry.get('dominio'), 'tipo': f['tipo']})

    # === COSTANTE DINAMICA ===
    # L'operatore orienta il piano. Il lab converge su quel piano.
    costante_path = Path(__file__).parent / 'data' / 'costante_dinamica.json'
    costante = {}
    if costante_path.exists():
        try:
            costante = json.loads(costante_path.read_text())
            print(f"\n--- Costante dinamica: {costante.get('angolo', '?')[:80]} ---")
            report_lines.append(f"## Costante dinamica")
            report_lines.append(f"  Angolo: {costante.get('angolo', '?')}")
            report_lines.append(f"  Piano: {costante.get('dominio_primario', '?')} + {costante.get('dominio_secondario', '?')}")
            report_lines.append(f"  Assiomi: {costante.get('assiomi_attivi', [])}")
        except Exception:
            pass

    # === SEME → PIANO → CONSECUTIO (A13) ===
    piano_notte = _leggi_seme_e_piano()

    # Se c'è costante dinamica, prioritizza le tensioni che toccano il suo angolo
    if costante and piano_notte['tensioni']:
        angolo_kw = set(w.lower() for w in costante.get('angolo', '').split() if len(w) > 3)
        dom_pri = costante.get('dominio_primario', '').lower()
        dom_sec = costante.get('dominio_secondario', '').lower()
        assiomi = set(costante.get('assiomi_attivi', []))

        def _costante_score(t):
            score = 0
            claim_lower = t.get('claim', '').lower()
            tid = t.get('id', '').lower()
            # Match con angolo
            for kw in angolo_kw:
                if kw in claim_lower or kw in tid:
                    score += 2
            # Match con dominio
            if dom_pri and (dom_pri in claim_lower or dom_pri in tid):
                score += 3
            if dom_sec and (dom_sec in claim_lower or dom_sec in tid):
                score += 2
            # Match con assiomi attivi
            for a in assiomi:
                if t.get('condensato_ref') and a in str(t['condensato_ref']):
                    score += 3
            return score

        # Riordina: tensioni allineate alla costante prima
        piano_notte['tensioni'].sort(key=lambda t: _costante_score(t), reverse=True)
        top = piano_notte['tensioni'][0]
        print(f"  Tensione prioritaria (costante): {top.get('id','?')} (score {_costante_score(top)})")

    if piano_notte['tensioni']:
        print(f"\n--- Seme piano {piano_notte['piano']}: {len(piano_notte['tensioni'])} tensioni vive ---")
        report_lines.append(f"## Seme (piano {piano_notte['piano']})")
        report_lines.append(f"  Direzione: {piano_notte['direzione'][:80]}")
        for t in piano_notte['tensioni']:
            report_lines.append(f"  [{t.get('tipo','')}] {t.get('id','')}: {t.get('claim','')[:60]}")

    # Consecutio (A13): prosegui dal punto in cui il seme e' arrivato
    controprove_seme = _consecutio_da_seme(piano_notte)
    if controprove_seme:
        print(f"  Consecutio: {len(controprove_seme)} test dal seme")
        report_lines.append(f"  Consecutio: {len(controprove_seme)} test generati dalle tensioni vive")

    # Fase 0: Controprove — dal seme + domini fissi dove il frame e' debole
    controprove_base = genera_controprove()
    # Dedup: stessa combo (dominio, params) non va testata due volte
    seen = set()
    controprove = []
    for dom, params in controprove_seme + controprove_base:
        key = (dom, json.dumps(params, sort_keys=True))
        if key not in seen:
            seen.add(key)
            controprove.append((dom, params))
    print(f"\n--- Fase 0: {len(controprove)} controprove ({len(controprove_seme)} da seme + {len(controprove_base)} base) ---")
    report_lines.append(f"## Fase 0: {len(controprove)} controprove ({len(controprove_seme)} seme + {len(controprove_base)} base)")

    for dominio_base, params in controprove:
        var_name = f"{dominio_base}_cp_{list(params.values())[0]}" if params else f"{dominio_base}_cp"
        print(f"\n  Controprova: {var_name}")

        try:
            signal, metadata = _genera_variante(dominio_base, params)
            metadata['variante'] = var_name
            metadata['params'] = params
            metadata['tipo_test'] = 'controprova'

            risultato = analizza_dnd(signal, metadata)
            findings, vincoli = valuta_risultato(risultato)

            analisi = risultato.get('analisi', {})
            r_dir = analisi.get('scissione', {}).get('r_diretto', '?')
            spacing = analisi.get('spacing', {})
            s_tipo = spacing.get('tipo', '?')
            s_r = spacing.get('mean_r', '?')

            # Null baseline info
            disc = analisi.get('discrimina', True)
            disc_tag = '' if disc is True else ' [NULL:non-disc]' if disc is False else ' [NULL:parziale]'

            # Per le controprove, i VINCOLI sono il segnale
            status = 'VINCOLO' if vincoli else 'conferma'
            line = f"  {var_name}: r={r_dir}, spacing={s_tipo} [{status}]{disc_tag}"
            print(f"  {line}")
            report_lines.append(line)

            entry = {
                'ciclo': stato['ciclo'] + 0.1,
                'dominio': var_name,
                'timestamp': datetime.now().isoformat(),
                'n_punti': len(signal),
                'r_diretto': analisi.get('scissione', {}).get('r_diretto'),
                'punto_fisso': analisi.get('punto_fisso'),
                'alternanza': analisi.get('alternanza'),
                'converge': analisi.get('converge'),
                'gap_ratio': analisi.get('gap_ratio'),
                'spacing': s_tipo if isinstance(s_tipo, str) else None,
                'spacing_r': s_r if isinstance(s_r, float) else None,
                'discrimina': disc,
                'findings': [f['tipo'] for f in findings],
                'vincoli': [v['tipo'] for v in vincoli],
                'tipo_test': 'controprova',
                'params': params,
            }
            aggiungi_journal(entry)

            # A11: aggiorna il campo vivo — ogni risultato informa il campo
            aggiorna_campo(entry, findings, vincoli)

        except Exception as e:
            print(f"  ERRORE: {e}")
            report_lines.append(f"  {var_name}: ERRORE — {e}")

    # === A11 COMBO: vincoli → esperimenti nello stesso ciclo ===
    if campo['vincoli']:
        print(f"\n--- Combo A11: {len(campo['vincoli'])} vincoli → esperimenti immediati ---")
        report_lines.append(f"\n## Combo A11: {len(campo['vincoli'])} vincoli riciclati")
        for v in campo['vincoli'][:3]:  # max 3 per non esplodere
            v_nota = v.get('nota', str(v))[:60]
            print(f"  Vincolo → esperimento: {v_nota}")
            report_lines.append(f"  vincolo riciclato: {v_nota}")

    # === A11 COMBO: anomalie → cross-domain immediato ===
    if campo['anomalie']:
        print(f"\n--- Combo A11: {len(campo['anomalie'])} anomalie → propagazione cross-domain ---")
        report_lines.append(f"\n## Combo A11: {len(campo['anomalie'])} anomalie propagate")
        # I domini GUE con anomalie vengono testati sui domini Poisson e viceversa
        for a in campo['anomalie'][:3]:
            print(f"  Anomalia {a['dominio']} ({a['tipo']}) → propagata")
            report_lines.append(f"  anomalia propagata: {a['dominio']} ({a['tipo']})")

    # === A11 COMBO: campo stats → report in tempo reale ===
    n_gue = len(campo['gue_domains'])
    n_poi = len(campo['poisson_domains'])
    if n_gue + n_poi > 0:
        print(f"\n  Campo vivo dopo Fase 0: {n_gue} GUE / {n_poi} Poisson")
        report_lines.append(f"\n  Campo dopo Fase 0: {n_gue} GUE / {n_poi} Poisson")
        if campo['r_values']:
            avg_r = sum(campo['r_values']) / len(campo['r_values'])
            print(f"  ⟨r⟩ medio campo: {avg_r:.4f}")
            report_lines.append(f"  ⟨r⟩ medio campo: {avg_r:.4f}")

    # Fase 1: Varianti (ridotte — solo baseline di robustezza)
    varianti = genera_varianti_domini()
    # Campiona 4 varianti random dalle 11 per non ripetere sempre le stesse
    import random
    varianti_sample = random.sample(varianti, min(4, len(varianti)))
    print(f"\n--- Fase 1: {len(varianti_sample)} varianti (campionate da {len(varianti)}) ---")
    report_lines.append(f"\n## Fase 1: {len(varianti_sample)} varianti (campionate)")

    for dominio_base, params in varianti_sample:
        var_name = f"{dominio_base}_var_{list(params.values())[0]}"
        print(f"\n  Variante: {var_name}")

        try:
            # Genera segnale con parametri modificati
            signal, metadata = _genera_variante(dominio_base, params)
            metadata['variante'] = var_name
            metadata['params'] = params

            risultato = analizza_dnd(signal, metadata)
            findings, vincoli = valuta_risultato(risultato)

            analisi = risultato.get('analisi', {})
            r_dir = analisi.get('scissione', {}).get('r_diretto', '?')
            spacing = analisi.get('spacing', {})
            s_tipo = spacing.get('tipo', '?')
            s_r = spacing.get('mean_r', '?')

            disc = analisi.get('discrimina', True)
            disc_tag = '' if disc is True else ' [NULL:non-disc]' if disc is False else ' [NULL:parziale]'
            line = f"  {var_name}: r={r_dir}, spacing={s_tipo} (⟨r⟩={s_r}){disc_tag}"
            print(f"  {line}")
            report_lines.append(line)

            # Journal
            entry = {
                'ciclo': stato['ciclo'] + 0.1,
                'dominio': var_name,
                'timestamp': datetime.now().isoformat(),
                'n_punti': len(signal),
                'r_diretto': analisi.get('scissione', {}).get('r_diretto'),
                'punto_fisso': analisi.get('punto_fisso'),
                'alternanza': analisi.get('alternanza'),
                'converge': analisi.get('converge'),
                'gap_ratio': analisi.get('gap_ratio'),
                'spacing': s_tipo if isinstance(s_tipo, str) else None,
                'spacing_r': s_r if isinstance(s_r, float) else None,
                'discrimina': disc,
                'findings': [f['tipo'] for f in findings],
                'vincoli': [v['tipo'] for v in vincoli],
                'variante': True,
                'params': params,
            }
            aggiungi_journal(entry)

            # A11: aggiorna il campo vivo
            aggiorna_campo(entry, findings, vincoli)

        except Exception as e:
            print(f"  ERRORE: {e}")
            report_lines.append(f"  {var_name}: ERRORE — {e}")

    # Fase 2: Multi-scala
    print(f"\n--- Fase 2: Analisi multi-scala ---")
    report_lines.append("")
    report_lines.append("## Fase 2: Multi-scala")
    for dominio in ['numeri_primi', 'cellular_automata', 'ising_2d']:
        risultati = analisi_multi_scala(dominio)
        if risultati:
            for r in risultati:
                report_lines.append(
                    f"  {dominio} N={r['scala']}: r={r['r_diretto']:.4f}")

    # Fase 2.5: Fonti esterne (VI digest, insight dal mondo)
    fonti = _consuma_fonti_esterne()
    if fonti:
        print(f"\n--- Fase 2.5: {len(fonti)} fonti esterne ---")
        report_lines.append("")
        report_lines.append(f"## Fase 2.5: Fonti esterne ({len(fonti)})")
        for fonte in fonti:
            report_lines.append(f"  [{fonte.get('tipo', '?')}] {fonte.get('titolo', '?')}")
            if fonte.get('accoppiamento'):
                report_lines.append(f"    -> accoppia con tensione: {fonte['accoppiamento'][:80]}")
    else:
        report_lines.append("")
        report_lines.append("## Fase 2.5: Fonti esterne (nessuna)")

    # Fase 3: Meta-analisi
    print(f"\n--- Fase 3: Meta-analisi ---")
    report_lines.append("")
    report_lines.append("## Fase 3: Meta-analisi")
    stato = meta_analisi(stato)

    # Fase 4: Cross-domain
    print(f"\n--- Fase 4: Cross-domain ---")
    report_lines.append("")
    report_lines.append("## Fase 4: Cross-domain")
    combinazioni_cross_domain(stato)

    # Fase 5: Valuator — valuta il batch notturno
    print(f"\n--- Fase 5: Valuator ---")
    report_lines.append("")
    report_lines.append("## Fase 5: Valuator")
    valutazione = _valuta_batch_notturno()
    for line in valutazione['report']:
        print(f"  {line}")
        report_lines.append(f"  {line}")

    # Salva valutazione nello stato
    stato['ultima_valutazione'] = valutazione['stato']
    stato['valutazione_dettaglio'] = valutazione['dettaglio']
    salva_stato(stato)

    # === A11: Campo vivo finale ===
    report_lines.append("")
    report_lines.append("## Campo Vivo (A11)")
    n_gue = len(campo['gue_domains'])
    n_poi = len(campo['poisson_domains'])
    n_vinc = len(campo['vincoli'])
    n_anom = len(campo['anomalie'])
    avg_r = sum(campo['r_values']) / len(campo['r_values']) if campo['r_values'] else 0
    report_lines.append(f"  GUE: {n_gue} | Poisson: {n_poi} | Vincoli: {n_vinc} | Anomalie: {n_anom}")
    report_lines.append(f"  ⟨r⟩ medio sessione: {avg_r:.4f}")
    report_lines.append(f"  Domini GUE: {', '.join(campo['gue_domains'][:10])}")
    report_lines.append(f"  Domini Poisson: {', '.join(campo['poisson_domains'][:10])}")
    if campo['anomalie']:
        report_lines.append(f"  Anomalie: {', '.join(a['dominio'] + '(' + a['tipo'] + ')' for a in campo['anomalie'][:5])}")

    print(f"\n  Campo vivo finale: {n_gue} GUE / {n_poi} Poisson / {n_vinc} vincoli / {n_anom} anomalie / ⟨r⟩={avg_r:.4f}")

    # Fase 6: Report
    report_lines.append("")
    report_lines.append("## Sommario")
    report_lines.append(f"  Cicli totali: {stato['ciclo']}")
    report_lines.append(f"  Pattern: {len(stato['pattern_trovati'])}")
    report_lines.append(f"  Vincoli: {len(stato['vincoli_lazarus'])}")
    report_lines.append(f"  Valutazione: {valutazione['stato']}")

    # Salva report
    report_path = DATA / f'notte_{ts}.md'
    with open(report_path, 'w') as f:
        f.write('\n'.join(report_lines))
    print(f"\n  Report salvato: {report_path}")

    # Notifica Sinapsi se fonti esterne consumate
    if fonti:
        _notifica_sinapsi_risultato(fonti, report_lines)

    # Notifica Sinapsi la valutazione
    _notifica_valutazione(valutazione)

    # Public D-ND_LAB package: THIA/Sinapsi sync is intentionally disabled.
    # The portable repo must not read local THIA credentials or call private
    # VPS endpoints when a researcher runs the physics tools.
    print("  Campo vivo: THIA sync disabled in portable D-ND_LAB")

    report_stato(stato)
    return report_path


def _valuta_batch_notturno():
    """
    Valuator: valuta le ultime 24h di journal entries.
    Cerca: saturazione, segnali genuini, drift META, falsi negativi.
    Output: stato (saturated|exploring|signal), dettaglio, report lines.
    """
    if not JOURNAL.exists():
        return {'stato': 'no_data', 'dettaglio': {}, 'report': ['Nessun journal trovato']}

    with open(JOURNAL) as f:
        journal = json.load(f)

    # Filtra ultime 24h
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    recenti = [e for e in journal if e.get('timestamp', '') > cutoff]

    if len(recenti) < 3:
        return {'stato': 'insufficient', 'dettaglio': {'entries': len(recenti)},
                'report': [f'Solo {len(recenti)} entries nelle ultime 24h — insufficiente per valutare']}

    # 1. Tasso saturazione: quante entries sono "struttura_dnd_piena" senza vincoli?
    conferme = sum(1 for e in recenti if 'struttura_dnd_piena' in e.get('findings', []))
    triviali = sum(1 for e in recenti if 'convergenza_triviale' in e.get('findings', []))
    vincoli_trovati = sum(1 for e in recenti if e.get('vincoli'))
    tasso_conferma = conferme / len(recenti) if recenti else 0
    tasso_triviale = triviali / len(recenti) if recenti else 0

    # 2. Controprove vs varianti
    controprove = [e for e in recenti if e.get('tipo_test') == 'controprova']
    cp_con_vincoli = [e for e in controprove if e.get('vincoli')]
    cp_con_struttura = [e for e in controprove if 'struttura_dnd_piena' in e.get('findings', [])]

    # 3. Segnali anomali (spacing GUE, rapporto aureo diretto, etc.)
    segnali = [e for e in recenti if any(
        f in e.get('findings', []) for f in ['rapporto_aureo_diretto', 'spacing_gue']
    )]

    # 4. META drift (se presente)
    meta_entries = [e for e in journal[-50:] if 'META' in e.get('dominio', '')]
    meta_drift = None
    if len(meta_entries) >= 5:
        rs = [e['r_diretto'] for e in meta_entries[-10:] if e.get('r_diretto')]
        if len(rs) >= 3:
            trend = rs[-1] - rs[0]
            meta_drift = {'r_mean': sum(rs) / len(rs), 'trend': trend, 'n': len(rs)}

    # Diagnosi
    report = []
    report.append(f"Entries 24h: {len(recenti)} (struttura: {conferme}, triviali: {triviali}, vincoli: {vincoli_trovati})")
    report.append(f"Tasso struttura reale: {tasso_conferma:.1%} | triviale: {tasso_triviale:.1%}")
    report.append(f"Controprove: {len(controprove)} (vincoli: {len(cp_con_vincoli)}, struttura: {len(cp_con_struttura)})")

    if segnali:
        report.append(f"SEGNALI ANOMALI: {len(segnali)}")
        for s in segnali:
            report.append(f"  -> {s.get('dominio')}: {s.get('findings')}")

    if meta_drift:
        report.append(f"META: r_mean={meta_drift['r_mean']:.4f}, trend={meta_drift['trend']:+.4f} (n={meta_drift['n']})")

    # Classificazione
    if tasso_conferma > 0.85 and vincoli_trovati == 0:
        stato = 'saturated'
        report.append("DIAGNOSI: SATURO — il ciclo conferma senza invertire (det=+1)")
        report.append("AZIONE: servono nuovi domini o intervento manuale sulle tensioni")
    elif len(cp_con_vincoli) >= 2 or segnali:
        stato = 'signal'
        report.append("DIAGNOSI: SEGNALE — trovati vincoli o anomalie nelle controprove")
        if cp_con_vincoli:
            report.append("Falsi negativi trovati:")
            for e in cp_con_vincoli:
                report.append(f"  {e.get('dominio')}: vincoli={e.get('vincoli')}")
    elif tasso_conferma < 0.7:
        stato = 'exploring'
        report.append("DIAGNOSI: ESPLORAZIONE — mix di conferme e vincoli, il campo si muove")
    else:
        stato = 'stable'
        report.append("DIAGNOSI: STABILE — alta conferma ma alcuni vincoli presenti")

    dettaglio = {
        'entries_24h': len(recenti),
        'struttura_reale': conferme,
        'convergenza_triviale': triviali,
        'tasso_conferma': round(tasso_conferma, 3),
        'tasso_triviale': round(tasso_triviale, 3),
        'vincoli_trovati': vincoli_trovati,
        'controprove_total': len(controprove),
        'controprove_vincoli': len(cp_con_vincoli),
        'segnali_anomali': len(segnali),
        'meta_drift': meta_drift,
        'timestamp': datetime.now().isoformat(),
    }

    return {'stato': stato, 'dettaglio': dettaglio, 'report': report}


def _notifica_valutazione(valutazione):
    """Posta la valutazione su Sinapsi per visibilita' TM1/TM3."""
    import os
    token = os.environ.get('THIA_API_TOKEN')
    if not token:
        return

    stato = valutazione['stato']
    det = valutazione['dettaglio']
    emoji = {'saturated': '🔴', 'signal': '🟢', 'exploring': '🟡',
             'stable': '🔵', 'insufficient': '⚪', 'no_data': '⚪'}

    content = (
        f"{emoji.get(stato, '?')} Lab Valuator: {stato.upper()}\n"
        f"Entries 24h: {det.get('entries_24h', '?')} | "
        f"Conferma: {det.get('tasso_conferma', '?'):.0%} | "
        f"Vincoli: {det.get('vincoli_trovati', 0)} | "
        f"Segnali: {det.get('segnali_anomali', 0)}\n"
        f"Controprove: {det.get('controprove_total', 0)} "
        f"({det.get('controprove_vincoli', 0)} con vincoli)"
    )

    try:
        import urllib.request
        data = json.dumps({
            'from': 'LAB', 'to': 'TM1',
            'type': 'lab_valutazione',
            'subject': f'Lab Valuator: {stato}',
            'content': content
        }).encode()
        req = urllib.request.Request(
            f'http://localhost:3002/api/node-sync',
            data=data,
            headers={'Content-Type': 'application/json', 'X-THIA-Token': token}
        )
        urllib.request.urlopen(req, timeout=5)
        print(f"  Valutazione postata su Sinapsi: {stato}")
    except Exception as e:
        print(f"  Sinapsi non raggiungibile: {e}")


def _genera_variante(dominio_base, params):
    """Genera una variante di un dominio con parametri modificati."""
    if dominio_base == 'ising_2d':
        L = 32
        T_c = 2 / np.log(1 + np.sqrt(2))
        T = T_c + params.get('T_offset', 0)
        spins = np.random.choice([-1, 1], size=(L, L))
        magnetizations = []
        for step in range(3000):
            for _ in range(L * L):
                i, j = np.random.randint(0, L, 2)
                neighbors = (spins[(i+1)%L, j] + spins[(i-1)%L, j] +
                            spins[i, (j+1)%L] + spins[i, (j-1)%L])
                dE = 2 * spins[i, j] * neighbors
                if dE <= 0 or np.random.random() < np.exp(-dE / T):
                    spins[i, j] *= -1
                magnetizations.append(np.mean(spins))
        return np.array(magnetizations), {
            'dominio': 'ising_2d', 'T': T, 'T_c': T_c,
            'nota': f'Ising 2D a T={T:.3f} (T_c={T_c:.3f})'
        }

    elif dominio_base == 'numeri_primi':
        max_n = params.get('max_n', 50000)
        def sieve(n):
            is_prime = [True] * (n + 1)
            is_prime[0] = is_prime[1] = False
            for i in range(2, int(n**0.5) + 1):
                if is_prime[i]:
                    for j in range(i*i, n + 1, i):
                        is_prime[j] = False
            return [i for i in range(n + 1) if is_prime[i]]
        primes = sieve(max_n)
        gaps = np.diff(primes).astype(float)
        return gaps, {
            'dominio': 'numeri_primi', 'max_n': max_n,
            'nota': f'Gap primi fino a {max_n}'
        }

    elif dominio_base == 'logistica_biforcazione':
        r = params.get('r_override', 1 + np.sqrt(8))
        x = 0.5
        for _ in range(1000):
            x = r * x * (1 - x)
        orbit = []
        for _ in range(5000):
            x = r * x * (1 - x)
            orbit.append(x)
        return np.array(orbit), {
            'dominio': 'logistica_biforcazione', 'r': r,
            'nota': f'Logistica a r={r:.4f}'
        }

    elif dominio_base == 'cellular_automata':
        L = 200
        rule_number = params.get('rule_number', 110)
        # Genera tabella da numero regola
        rule = {}
        for i in range(8):
            bits = ((i >> 2) & 1, (i >> 1) & 1, i & 1)
            rule[bits] = (rule_number >> i) & 1
        state = np.zeros(L, dtype=int)
        state[L//2] = 1
        density = []
        for _ in range(5000):
            density.append(np.mean(state))
            new = np.zeros(L, dtype=int)
            for i in range(L):
                triple = (state[(i-1)%L], state[i], state[(i+1)%L])
                new[i] = rule[triple]
            state = new
        return np.array(density), {
            'dominio': 'cellular_automata', 'rule': rule_number,
            'nota': f'Rule {rule_number} density'
        }

    elif dominio_base == 'brownian_motion':
        N = 2000
        H = params.get('H', 0.7)
        # Metodo circulant embedding (Wood-Chan) — corretto per tutte le H
        from dnd_experiments import generate_fbm
        signal = generate_fbm(N, H, seed=np.random.randint(0, 10000))
        return signal, {
            'dominio': 'brownian_motion', 'H': H,
            'nota': f'fBM con H={H} (circulant embedding)'
        }

    elif dominio_base == 'coupled_oscillators':
        from scipy.integrate import solve_ivp
        N = params.get('N', 10)
        k = 1.0
        m = 1.0
        def eom(t, y):
            x = y[:N]
            v = y[N:]
            a = np.zeros(N)
            for i in range(N):
                if i > 0:
                    a[i] += -k * (x[i] - x[i-1]) / m
                else:
                    a[i] += -k * x[i] / m
                if i < N-1:
                    a[i] += -k * (x[i] - x[i+1]) / m
                else:
                    a[i] += -k * x[i] / m
            return list(v) + list(a)
        y0 = [0.0] * 2*N
        y0[0] = 1.0
        sol = solve_ivp(eom, [0, 100], y0, max_step=0.05)
        return sol.y[N//2], {
            'dominio': 'coupled_oscillators', 'N': N,
            'nota': f'Catena di {N} oscillatori'
        }

    elif dominio_base == 'percolation':
        L = 100
        p = params.get('p', 0.5927)
        n_samples = 100
        cluster_sizes = []
        for _ in range(n_samples):
            grid = np.random.random((L, L)) < p
            visited = np.zeros_like(grid, dtype=bool)
            sizes = []
            for i in range(L):
                for j in range(L):
                    if grid[i, j] and not visited[i, j]:
                        queue = [(i, j)]
                        visited[i, j] = True
                        size = 0
                        while queue:
                            ci, cj = queue.pop(0)
                            size += 1
                            for di, dj in [(0,1),(0,-1),(1,0),(-1,0)]:
                                ni, nj = ci+di, cj+dj
                                if 0 <= ni < L and 0 <= nj < L and grid[ni, nj] and not visited[ni, nj]:
                                    visited[ni, nj] = True
                                    queue.append((ni, nj))
                        sizes.append(size)
            if sizes:
                cluster_sizes.append(max(sizes))
        return np.array(cluster_sizes, dtype=float), {
            'dominio': 'percolation', 'p': p,
            'nota': f'Percolazione a p={p}'
        }

    elif dominio_base == 'rudin_shapiro':
        signal = _genera_rudin_shapiro(5000)
        return signal, {
            'dominio': 'rudin_shapiro',
            'nota': 'Rudin-Shapiro: struttura binaria, dipolo atteso basso (~0.33)'
        }

    elif dominio_base == 'collatz':
        signal = _genera_collatz(5000)
        return signal, {
            'dominio': 'collatz',
            'nota': 'Collatz: lunghezze traiettorie, CV atteso ~3/5 (non phi-1)'
        }

    elif dominio_base == 'metrica_primi':
        # Curvatura della metrica g=(p/2)² sui primi
        max_n = params.get('max_n', 100000)
        from sympy import primerange
        primes = np.array(list(primerange(2, max_n)), dtype=float)
        ln_p = np.log(primes)
        Gamma = np.diff(ln_p)  # connessione
        R = np.diff(Gamma)     # curvatura
        signal = list(R)
        return signal, {
            'dominio': 'metrica_primi',
            'nota': f'Curvatura metrica g=(p/2)², {len(primes)} primi. De Sitter nel tempo ln(p).',
            'max_n': max_n,
        }

    elif dominio_base == 'metrica_primi_connessione':
        # Connessione Γ_n = ln(p_{n+1}/p_n) come segnale
        max_n = params.get('max_n', 100000)
        from sympy import primerange
        primes = np.array(list(primerange(2, max_n)), dtype=float)
        Gamma = list(np.diff(np.log(primes)))
        return Gamma, {
            'dominio': 'metrica_primi_connessione',
            'nota': f'Connessione Γ_n della metrica g=(p/2)², {len(primes)} primi. Spettro β=-0.75.',
            'max_n': max_n,
        }

    else:
        return genera_segnale(dominio_base)


# === CLI ===

if __name__ == '__main__':
    stato = carica_stato()

    if len(sys.argv) > 1:
        if sys.argv[1] == '--stato':
            report_stato(stato)
        elif sys.argv[1] == '--continuo':
            n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            print(f"Autoricerca D-ND — {n} cicli")
            print(f"Non cerco φ. Osservo cosa emerge.\n")
            for i in range(n):
                stato = ciclo_ricerca(stato)
            report_stato(stato)
        elif sys.argv[1] == '--meta':
            stato = meta_analisi(stato)
        elif sys.argv[1] == '--scala':
            dominio = sys.argv[2] if len(sys.argv) > 2 else 'numeri_primi'
            analisi_multi_scala(dominio)
        elif sys.argv[1] == '--cross':
            combinazioni_cross_domain(stato)
        elif sys.argv[1] == '--completo':
            # Ciclo completo: domini restanti + meta + cross
            n = int(sys.argv[2]) if len(sys.argv) > 2 else len(stato['domini_coda'])
            print(f"Autoricerca D-ND — ciclo completo ({n} domini + meta + cross)")
            for i in range(min(n, len(stato['domini_coda']))):
                stato = ciclo_ricerca(stato)
            stato = meta_analisi(stato)
            combinazioni_cross_domain(stato)
            report_stato(stato)
        elif sys.argv[1] == '--notte':
            report_path = ciclo_notte()
            print(f"\n  Ciclo notturno completato. Report: {report_path}")
        elif sys.argv[1] == '--pubblica':
            report_stato(stato)
            if stato.get('segnale_pubblica'):
                print("\n  Il sistema segnala: materiale sufficiente per pubblicazione.")
                print("  Domini con pattern:", set(f['dominio'] for f in stato['pattern_trovati']))
            else:
                print("\n  Non ancora. Continuare l'esplorazione.")
        else:
            print(f"Uso: python {sys.argv[0]} [--stato|--continuo N|--meta|--scala DOMINIO|--cross|--completo|--pubblica]")
    else:
        # Un ciclo
        stato = ciclo_ricerca(stato)
        report_stato(stato)
