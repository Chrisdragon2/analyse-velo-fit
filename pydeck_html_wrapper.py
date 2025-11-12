# --- Fichier: pydeck_html_wrapper.py ---
import streamlit as st
import pydeck as pdk
import json 

def generate_deck_html(pydeck_object: pdk.Deck, mapbox_key: str) -> str:
    """
    Génère un fichier HTML autonome pour un objet Pydeck en utilisant un 
    template JS personnalisé qui active le MapController 3D et 
    utilise les bonnes versions CDN.
    """
    
    # 1. Obtenir la spécification JSON (format v8)
    # On utilise .to_json() pour obtenir la spécification complète
    deck_json = pydeck_object.to_json()
    
    # 2. On doit s'assurer que le JSON est une chaîne JavaScript valide
    # en utilisant json.dumps() pour l'échappement des guillemets, etc.
    # C'est cette chaîne qui sera injectée dans le code JS.
    deck_json_string_for_js = json.dumps(deck_json)

    # 3. Définir le template HTML/JS
    html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Pydeck 3D Map</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <!-- Utilisation de versions CDN stables et compatibles -->
    <script src="https://unpkg.com/deck.gl@8.8.0/dist.min.js"></script>
    <script src="https://api.mapbox.com/mapbox-gl-js/v2.13.0/mapbox-gl.js"></script>
    <link href="https://api.mapbox.com/mapbox-gl-js/v2.13.0/mapbox-gl.css" rel="stylesheet" />
    
    <style>
        /* S'assurer que la carte prend toute la place disponible */
        body {{ margin: 0; padding: 0; height: 100vh; width: 100vw; overflow: hidden; }}
        #deck-gl-map {{ height: 100%; width: 100%; background-color: #000; }}
    </style>
</head>
<body style="margin:0; padding:0; height:100vh; width:100%;">
    <div id="deck-gl-map"></div>

    <script type="text/javascript">
        // 1. Définir la clé Mapbox
        mapboxgl.accessToken = "{mapbox_key}";

        // 2. Recevoir la spécification JSON injectée depuis Python
        // On utilise JSON.parse() pour convertir la chaîne en objet JavaScript
        const pydeckSpec = JSON.parse({deck_json_string_for_js});

        // 3. Instancier Deck.gl
        const deckInstance = new deck.Deck({{
           ...pydeckSpec,
            
            // FORCER l'activation du contrôleur 3D pour la navigation
            controller: true, 
            
            // Définir le conteneur
            container: 'deck-gl-map',
            
            // S'assurer que la VUE est passée
            initialViewState: pydeckSpec.initialViewState,
            
            // S'assurer que la CLÉ est passée pour Mapbox
            mapboxApiAccessToken: "{mapbox_key}" 
        }});

    </script>
</body>
</html>
"""
    return html_template
