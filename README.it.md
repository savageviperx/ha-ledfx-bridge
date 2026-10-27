# LedFx HA Bridge

Un’integrazione personalizzata per far reagire alla musica di LedFx le luci RGB già presenti in Home Assistant. Riceve un pixel DDP ed esegue direttamente le azioni della luce in HA: **non servono EXE né token HA**.

LedFx continua a funzionare sul PC per acquisire l’audio e generare gli effetti. Questa integrazione convive con `hass-ledfx` e non lo sostituisce per la gestione degli effetti.

## Installazione HACS

Richiede Home Assistant 2025.6 o successivo e una luce con controllo colore già funzionante in HA.

1. HACS → **⋮ → Repository personalizzati**.
2. Inserisci `https://github.com/savageviperx/ha-ledfx-bridge` e seleziona **Integrazione**.
3. Scarica **LedFx HA Bridge** e riavvia Home Assistant.
4. **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → LedFx HA Bridge**.
5. Scegli nome, entità luce e porta UDP, inizialmente **4048**. L’IP del PC LedFx è facoltativo: se inserito, filtra la sorgente dei pacchetti e aggiunge il collegamento alla sua interfaccia web.

Per altre luci aggiungi un’altra associazione, con una porta diversa: 4049, 4050 e così via. Le porte e le entità duplicate vengono rifiutate. Il repository va aggiunto manualmente: la pubblicazione su GitHub non equivale all’inserimento nel catalogo predefinito HACS.

Dalla v0.1.1 è inclusa l’icona dell’app, visualizzata localmente da **Home Assistant 2026.3 o successivo** anche come logo e nei temi scuri. Dopo l’aggiornamento da HACS, riavvia HA e aggiorna la pagina o l’app. Le versioni HA precedenti possono usare il bridge, ma non mostrano l’icona inclusa.

## Configurazione LedFx

Per ogni luce crea un dispositivo **DDP**:

| Impostazione | Valore |
| --- | --- |
| IP | **IP locale di Home Assistant** |
| Porta | La porta UDP scelta, per esempio **4048** |
| Numero pixel | **1** |
| Destination ID | **1** |
| Frequenza | Almeno 30 FPS |
| Preview only | Disattivato |

Assegna un effetto che reagisce all’audio e seleziona l’ingresso corretto. La porta web LedFx, normalmente **8888**, è distinta dalla porta DDP. L’IP della lampadina non serve.

Il PC deve raggiungere HA sulla porta UDP configurata, anche se si trova in un’altra sottorete. Reti guest o isolamento Wi-Fi possono impedirlo. Con HA Container servono rete host oppure le porte UDP pubblicate, per esempio `4048:4048/udp`.

## Uso e prestazioni

Ogni associazione crea un interruttore **Sincronizzazione musicale**, sensori di ricezione/stato e due sensori diagnostici facoltativi per invii al secondo e latenza. L’interruttore ripristina lo stato precedente al riavvio; mettendolo su off si fermano i nuovi invii, mentre quelli già partiti possono completarsi.

I valori iniziali sono **massimo 20 invii/s, 4 chiamate contemporanee e soglia RGB 1**. Si tiene solo il colore più recente, senza accumulare una coda. Un errore sospende temporaneamente gli invii; i pacchetti scadono dopo 5 secondi e la luce mantiene l’ultimo colore.

**Configura** permette di modificare frequenza (1–60), concorrenza (1–8) e soglia. **⋮ → Riconfigura** cambia entità, IP o porte. L’inglese è la lingua di fallback; l’italiano segue la lingua dell’utente HA.

20 invii/s non garantiscono 20 cambiamenti fisici/s: Tuya cloud può introdurre limiti e ritardi. Le richieste contemporanee possono concludersi fuori ordine; imposta concorrenza 1 se preferisci l’ordine alla frequenza. La latenza mostrata misura la chiamata HA, non la risposta fisica della lampadina. Evita che il vecchio programma o altre automazioni comandino contemporaneamente la stessa luce.

## Debug

Dal menu dell’integrazione in HA puoi abilitare i **log di debug**, riprodurre il problema e poi disabilitarli per scaricarli. Gli aggiornamenti RGB restano a livello debug. **Scarica diagnostica** contiene contatori e impostazioni senza nomi, IP, entità o token. I sensori diagnostici più frequenti sono disabilitati inizialmente per limitare le scritture nello storico.

Se **Ricezione LedFx** è off, verifica destinazione DDP, pixel, effetto, filtro sorgente e rete UDP. Se è on, controlla interruttore di sincronizzazione e funzionamento della luce nella propria integrazione. La porta UDP non può essere condivisa con un altro ricevitore.

Per installazione manuale copia `custom_components/ledfx_bridge` nella cartella `custom_components` della configurazione HA e riavvia. Per rimuoverla elimina prima le associazioni da Dispositivi e servizi, poi disinstalla i file con HACS o manualmente.

[Documentazione completa in inglese](README.md) · [Validazione](VALIDATION.md)
