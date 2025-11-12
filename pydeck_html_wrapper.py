# --- Fichier: pydeck_html_wrapper.py (Corrigé pour la ValueError) ---
import streamlit as st
import pydeck as pdk
import json 

def generate_deck_html(pydeck_object: pdk.Deck, mapbox_key: str) -> str:
    """
    Génère un fichier HTML autonome pour un objet Pydeck en utilisant un 
    template JS personnalisé qui active le MapController 3D et, 
    surtout, utilise le JSONConverter pour instancier 
    correctement les couches (comme TerrainLayer).
    """
    
    # 1. Obtenir la spécification JSON (format v8)
    deck_json = pydeck_object.to_json()
    
    # 2. Le dumper en une chaîne JSON valide.
    deck_json_string = json.dumps(deck_json)

    # 3. Définir le template HTML/JS
    html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Pydeck 3D Map</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <script src="https://unpkg.com/deck.gl@8.8.0/dist.min.js"></script>
    <script src="https://unpkg.com/@deck.gl/json@8.8.0/dist.min.js"></script>
    <script src="https://api.mapbox.com/mapbox-gl-js/v2.13.0/mapbox-gl.js"></script>
    <link href="https://api.mapbox.com/mapbox-gl-js/v2.13.0/mapbox-gl.css" rel="stylesheet" />
    
    <style>
        body {{ margin: 0; padding: 0; height: 100vh; width: 100vw; overflow: hidden; }}
        #deck-gl-map {{ height: 100%; width: 100%; background-color: #000; }}
    </style>
</head>
<body style="margin:0; padding:0; height:100vh; width:100%;">
    <div id="deck-gl-map"></div>

    <script id="pydeck-spec-data" type="application/json">
    {deck_json_string}
    </script>

    <script type="text/javascript">
        mapboxgl.accessToken = "{mapbox_key}";

        // --- SECTION JAVASCRIPT CORRIGÉE ---
        
        // NOUVELLE ÉTAPE 2 : LIRE LE JSON DEPUIS LA BALISE SCRIPT
        const pydeckSpecJSON = document.getElementById('pydeck-spec-data').textContent;
        const pydeckSpec = JSON.parse(pydeckSpecJSON);

        // 3. INSTANCIER LE JSONCONVERTER
        // CORRECTION : Notez les accolades doublées {{ ... }}
        // C'est nécessaire pour le f-string de Python.
        const jsonConverter = new deck.JSONConverter({{
            configuration: {{
                // Cela dit au convertisseur : "Quand tu vois 'TerrainLayer',
                // utilise 'deck.TerrainLayer'"
                classes: {{ ...deck }}
            }}
        }});

        // 4. CONVERTIR LA SPÉCIFICATION JSON EN PROPS DECK.GL
        const deckProps = jsonConverter.convert(pydeckSpec);

        // 5. INSTANCIER DECK.GL AVEC LES BONNES PROPS
        // CORRECTION : accolades doublées {{ ... }} ici aussi.
        const deckInstance = new deck.Deck({{
            // On 'spread' les props converties (layers, views, etc.)
            ...deckProps,
            
            // On ajoute/force les props nécessaires pour
            // l'intégration dans notre HTML
            controller: true,
            container: 'deck-gl-map',
            mapboxApiAccessToken: "{mapbox_key}"
        }});

    </script>
</body>
</html>
"""
    return html_template
