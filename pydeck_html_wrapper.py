# --- Fichier: pydeck_html_wrapper.py ---
import streamlit as st
import pydeck as pdk
import json

def generate_deck_html(pydeck_object: pdk.Deck, mapbox_key: str) -> str:
    """
    Génère un fichier HTML autonome pour un objet Pydeck en utilisant un 
    template JS personnalisé qui active le MapController 3D.
   
    """
    
    # 1. Obtenir la spécification JSON de l'objet Deck
    # Nous utilisons to_json() et non to_html()
    deck_json_string = pydeck_object.to_json()

    # 2. Définir le template HTML/JS
    html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Pydeck 3D Map</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <script src="https://unpkg.com/deck.gl@latest/dist.min.js"></script>
    <script src="https://unpkg.com/mapbox-gl@latest/dist/mapbox-gl.js"></script>
    
    <style>
        body {{ 
            margin: 0; 
            padding: 0; 
            height: 100vh; 
            width: 100vw; 
            overflow: hidden; 
        }}
        #deck-gl-map {{ 
            height: 100%; 
            width: 100%; 
            background-color: #000; /* Fond noir par défaut */
        }}
    </style>
</head>
<body style="margin:0; padding:0; height:100vh; width:100%;">
    
    <div id="deck-gl-map"></div>

    <script type="text/javascript">
        // Définir la clé Mapbox (nécessaire pour TerrainLayer)
        // C'est sécurisé car tu as restreint l'URL de cette clé
        mapboxgl.accessToken = "{mapbox_key}";

        // 1. Recevoir la spécification JSON injectée depuis Python
        const pydeckSpec = {deck_json_string};

        // 2. Instancier Deck.gl CORRECTEMENT
        const deckInstance = new deck.Deck({{
            
            // 3. Déstructurer la spécification Pydeck
            // (contient tes couches, map_style=None, initialViewState, etc.)
           ...pydeckSpec,
            
            // 4. FORCER l'activation du contrôleur 3D (LA CORRECTION)
            // Active le zoom, le panoramique et la rotation
            controller: true,
            
            // 5. Spécifier le conteneur
            container: 'deck-gl-map',
            
            // 6. S'assurer que le ViewState est passé (unifie les altitudes)
            initialViewState: pydeckSpec.initialViewState
        }});

    </script>
</body>
</html>
"""
    return html_template
