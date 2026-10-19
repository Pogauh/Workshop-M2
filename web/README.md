# PayAlpha (interface de paiement)

Application React 18 + Tailwind 3 (Vite). Servie par le conteneur `web`, **jamais exposée directement** : le WAF (`:8080`) route `/` vers elle,
`/auth/login` vers l'authentification et `/api/*` vers l'API.

- Connexion, solde, nouveau paiement, historique, reçu imprimable à l'écran.
- **Reprise sans double débit** : chaque paiement part avec une clé d'idempotence ; si le service est interrompu (attaque, redémarrage par
  le moteur de remédiation), l'interface rejoue la même clé jusqu'à ~40 s. Le serveur ne débite jamais deux fois.
- La bande « Service opérationnel » mesure la disponibilité réelle depuis le navigateur (même chemin que les paiements).
- Les mesures de sécurité sont visibles pour le client : compte verrouillé, suspendu, session révoquée, réinitialisation requise.

Développement : `npm install && npm run dev` (proxy vers `http://localhost:8080`). Tests de la logique client : `npm test` (Node ≥ 20, sans dépendance).
Jeton de session : `sessionStorage` uniquement (effacé à la fermeture de l'onglet), CSP stricte côté WAF.
