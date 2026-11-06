# Service Order (MSOA Shop)

Microservice de gestion des commandes du projet MSOA Shop (Lab 2, Microservice-oriented Architectures).
Technologie : Python, Flask, SQLite. Port : **8084**.

## Responsabilité

Le service Order est propriétaire des données de commande (tables `orders` et `order_items` dans `orders.db`) et **coordonne** la création et l'annulation d'une commande en appelant les autres services :

| Service   | Port | Rôle vis-à-vis de Order                                  |
|-----------|------|----------------------------------------------------------|
| Catalog   | 8082 | Fournit le nom et le prix de chaque produit              |
| Inventory | 8083 | Réserve le stock à la création, le libère à l'annulation |
| Shipping  | 8086 | Indique si une commande a déjà été expédiée              |

## Installation

```
cd order-service
python -m venv venv
venv\Scripts\activate
python -m pip install flask flask-cors requests
```

## Lancement

Mode autonome (par défaut) : aucun appel aux autres services, prix à 0.

```
python app.py
```

Mode intégré : appelle Catalog, Inventory et Shipping.

```
$env:STANDALONE="0"
python app.py
```

Variables d'environnement :

| Variable       | Défaut                  | Description                         |
|----------------|-------------------------|-------------------------------------|
| `STANDALONE`   | `1`                     | `1` = seul, `0` = avec les autres   |
| `CATALOG_URL`  | `http://localhost:8082` | URL du service Catalog              |
| `INVENTORY_URL`| `http://localhost:8083` | URL du service Inventory            |
| `SHIPPING_URL` | `http://localhost:8086` | URL du service Shipping             |

Vérification : `http://localhost:8084/health`

## Base de données

Fichiers fournis dans le TP : `orders.db`, `schema.sql`, `seed.sql`.
Pour afficher le contenu des tables : `python view_db.py`.

## API REST

| Méthode | Route                        | Description                          |
|---------|------------------------------|--------------------------------------|
| GET     | `/health`                    | État du service                      |
| GET     | `/api/orders?userId=...`     | Commandes d'un utilisateur           |
| GET     | `/api/orders/{id}`           | Une commande (404 si absente)        |
| POST    | `/api/orders`                | Crée une commande                    |
| PATCH   | `/api/orders/{id}/status`    | Change le statut                     |
| POST    | `/api/orders/{id}/cancel`    | Annule une commande                  |

Exemple de création :

```json
{
  "userId": "user-1",
  "customer": { "name": "Test", "address": "1 rue A", "city": "Casablanca" },
  "items": [ { "productId": 2, "quantity": 1 } ]
}
```

Les erreurs renvoient un JSON `{ "message": "...", "error": "..." }`.

## Statuts et transitions

```
PENDING_PAYMENT -> PAID | CANCELLED
PAID            -> SHIPPED | CANCELLED
SHIPPED         -> DELIVERED
DELIVERED, CANCELLED : états finaux
```

## Scénario de création d'une commande

1. Pour chaque article, Order demande le nom et le prix à Catalog (`GET /products/{id}`).
2. Order demande la réservation du stock à Inventory (`POST /api/inventory/reserve`).
3. Si le stock est insuffisant, la commande est **refusée (409)** et rien n'est enregistré.
4. Sinon, Order enregistre la commande avec le statut `PENDING_PAYMENT`.
5. Si l'enregistrement échoue, Order libère le stock réservé (compensation).

## Scénario d'annulation

1. Seules les commandes `PENDING_PAYMENT` ou `PAID` peuvent être annulées.
2. Order interroge Shipping (`GET /api/shipments/order/{id}`) : l'annulation est refusée si la livraison est déjà partie.
3. Order libère le stock chez Inventory (`POST /api/inventory/release`).
4. Le statut passe à `CANCELLED`.

Si un service dont Order dépend est arrêté, la réponse est `503`.

## Intégration avec le frontend

Dans `src/config/backend.js` du frontend, il suffit de mettre :

```js
ORDERS: "rest",
```

## Tests rapides (PowerShell)

```
Invoke-RestMethod http://localhost:8084/api/orders?userId=user-1

Invoke-RestMethod -Method Post -Uri http://localhost:8084/api/orders -ContentType "application/json" -Body '{"userId":"user-1","customer":{"name":"Test","address":"1 rue A","city":"Casablanca"},"items":[{"productId":2,"quantity":1}]}'
```

`mock_services.py` simule Catalog, Inventory et Shipping pour tester Order seul : `python mock_services.py`.