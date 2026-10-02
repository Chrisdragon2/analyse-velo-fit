# Politique de confidentialité — Générer CV ATS

**Dernière mise à jour : 2 octobre 2026**

## Finalité de l’extension

L’extension aide l’utilisateur à générer et archiver un CV à partir du texte d’une offre d’emploi sélectionnée dans Chrome. Elle analyse localement la page ouverte afin de proposer le nom de l’entreprise et l’intitulé du poste, puis envoie uniquement les informations nécessaires au backend Google Apps Script configuré par l’utilisateur lorsque celui-ci clique sur « Générer et archiver ».

## Données traitées

L’extension peut traiter les catégories suivantes :

- contenu du site web : texte de l’offre sélectionnée et contexte de page utilisé localement pour la détection ;
- activité de navigation limitée à la page utilisée : URL et titre de la page de l’offre ;
- informations saisies ou confirmées par l’utilisateur : entreprise, poste et langue du CV ;
- informations techniques de la demande : date, horodatage et identifiant de demande ;
- information d’authentification : token partagé saisi par l’utilisateur pour autoriser les appels vers son backend Apps Script.

## Utilisation locale

Le contexte complet de la page, les candidats de détection et le diagnostic de détection restent locaux dans Chrome. Ils ne sont pas envoyés au backend. L’extension ne collecte pas les pages en arrière-plan et n’analyse une page qu’après une action explicite de l’utilisateur.

## Données transmises

Lorsque l’utilisateur clique sur « Générer et archiver », l’extension transmet par HTTPS au backend Google Apps Script configuré par l’utilisateur : le texte sélectionné, l’URL, le titre de page, l’entreprise et le poste confirmés, la langue choisie, la date, l’horodatage, l’identifiant de demande et le token d’authentification. Ces données sont utilisées uniquement pour générer le CV et archiver la candidature dans le Google Drive de l’utilisateur.

## Stockage

L’URL du backend et le token sont stockés localement dans le profil Chrome de l’utilisateur. Les données temporaires de candidature sont stockées dans la session Chrome et sont supprimées à la fermeture du navigateur. Les fichiers générés et archivés sont stockés dans le Google Drive associé au backend configuré par l’utilisateur.

## Partage et vente de données

Les données ne sont ni vendues, ni utilisées pour la publicité, ni partagées avec des courtiers en données. Elles sont transmises uniquement aux services Google nécessaires au fonctionnement choisi par l’utilisateur, notamment Google Apps Script et Google Drive, afin de générer et stocker les fichiers demandés.

## Code distant et suivi

L’extension n’exécute aucun code distant et n’intègre aucun outil publicitaire ou analytique tiers.

## Sécurité

Les transmissions vers le backend sont effectuées via HTTPS. Le token n’est pas intégré au code de l’extension et doit être saisi par l’utilisateur. Il est conservé dans le stockage local de Chrome.

## Suppression des données

L’utilisateur peut supprimer la configuration locale en désinstallant l’extension. Les fichiers créés dans Google Drive peuvent être supprimés directement par l’utilisateur depuis son compte Google Drive.

## Limited Use

The use of information received from Google APIs will adhere to the Chrome Web Store User Data Policy, including the Limited Use requirements.

## Contact

Le contact développeur indiqué sur la fiche Chrome Web Store peut être utilisé pour toute question relative à cette politique.
