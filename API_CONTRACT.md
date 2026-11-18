# Contrat d'API - Service Order (v1.0)

Service : Order | Technologie : Flask + SQLite | Base URL : `http://localhost:8084`

## Conventions

- En-tête de requête avec corps : `Content-Type: application/json`
- En-tête `Authorization: Bearer <jeton>` : envoyé par le frontend, **non vérifié** par le service dans cette version.
- Toutes les réponses (succès et erreurs) sont en JSON.
- Identifiant utilisateur : `userId` (le service Payments utilise `customerId` pour la même information : nom commun à décider en équipe).

### Schéma Order (réponse)

| Champ | Type | Description |
|---|---|---|
| `id` | string (UUID) | Identifiant de la commande |
| `userId` | string | Utilisateur propriétaire |
| `customer` | objet | `{ "name": string, "address": string, "city": string }` |
| `items` | tableau | Lignes de commande (voir ci-dessous) |
| `items[].productId` | integer | Identifiant du produit |
| `items[].name` | string | Nom du produit (copié depuis Catalog à la commande) |
| `items[].price` | number | Prix unitaire (copié depuis Catalog à la commande) |
| `items[].quantity` | integer | Quantité (> 0) |
| `total` | number | Somme de `price * quantity` |
| `status` | string | `PENDING_PAYMENT`, `PAID`, `SHIPPED`, `DELIVERED` ou `CANCELLED` |
| `createdAt` | string (ISO 8601) | Date de création |

### Schéma d'erreur (tous les codes d'erreur)

```json
{ "message": "Order not found.", "error": "Order not found." }
```

| Champ | Type | Description |
|---|---|---|
| `message` | string | Message lisible, lu par le frontend |
| `error` | string | Même valeur (compatibilité) |

---

## 1. Lister les commandes d'un utilisateur

- **Opération** : consulter l'historique d'un utilisateur
- **Méthode et route** : `GET /api/orders`
- **But** : retourner les commandes d'un utilisateur, de la plus récente à la plus ancienne
- **Paramètre d'URL (query)** : `userId` (string, obligatoire)
- **En-têtes requis** : aucun
- **Corps** : aucun
- **Succès** : `200 OK`, tableau de commandes (schéma Order), tableau vide si aucune commande

| Code | Cas | Message |
|---|---|---|
| 400 | `userId` absent | `userId is required.` |

Exemple : `GET /api/orders?userId=user-1`

## 2. Consulter une commande

- **Méthode et route** : `GET /api/orders/{id}`
- **But** : retourner une commande par son identifiant
- **Paramètre d'URL** : `id` (string, obligatoire)
- **Corps** : aucun
- **Succès** : `200 OK`, objet Order

| Code | Cas | Message |
|---|---|---|
| 404 | commande inexistante | `Order not found.` |

## 3. Créer une commande

- **Méthode et route** : `POST /api/orders`
- **But** : créer une commande. Le service lit nom et prix chez Catalog, réserve le stock chez Inventory, puis enregistre la commande avec le statut `PENDING_PAYMENT`.
- **En-tête requis** : `Content-Type: application/json`
- **Corps de la requête** :

| Champ | Type | Obligatoire | Règle |
|---|---|---|---|
| `userId` | string | oui | non vide |
| `customer` | objet | oui | contient `name`, `address`, `city` |
| `customer.name` | string | oui | non vide |
| `customer.address` | string | oui | non vide |
| `customer.city` | string | oui | non vide |
| `items` | tableau | oui | non vide |
| `items[].productId` | integer | oui | doit exister dans Catalog |
| `items[].quantity` | integer | oui | supérieur à 0 |

```json
{
  "userId": "user-1",
  "customer": { "name": "Test", "address": "1 rue A", "city": "Casablanca" },
  "items": [ { "productId": 2, "quantity": 1 } ]
}
```

- **Succès** : `201 Created`, objet Order (statut `PENDING_PAYMENT`)

| Code | Cas | Message (exemple) |
|---|---|---|
| 400 | liste `items` vide | `Cannot create an empty order.` |
| 400 | `customer.name`, `address` ou `city` manquant | `Customer name, address and city are required.` |
| 400 | quantité <= 0 | `Quantity must be positive.` |
| 400 | produit inconnu ou ligne invalide | `Product 99 not found.` |
| 401 | `userId` absent | `Authentication required.` |
| 409 | stock insuffisant (aucune commande créée) | `Insufficient stock for product 2.` |
| 500 | échec de l'enregistrement (stock libéré) | `Could not save the order.` |
| 503 | Catalog ou Inventory indisponible | `Catalog service unavailable.` / `Inventory service unavailable.` |

## 4. Changer le statut d'une commande

- **Méthode et route** : `PATCH /api/orders/{id}/status`
- **But** : faire avancer le statut (utilisé par Payments, Shipping, ou le frontend)
- **Paramètre d'URL** : `id` (string)
- **En-tête requis** : `Content-Type: application/json`
- **Corps** : `{ "status": "PAID" }` avec `status` (string, obligatoire)
- **Transitions autorisées** :

| Statut actuel | Statuts possibles |
|---|---|
| `PENDING_PAYMENT` | `PAID`, `CANCELLED` |
| `PAID` | `SHIPPED`, `CANCELLED` |
| `SHIPPED` | `DELIVERED` |
| `DELIVERED`, `CANCELLED` | aucun |

- **Succès** : `200 OK`, objet Order mis à jour

| Code | Cas | Message (exemple) |
|---|---|---|
| 400 | transition interdite ou statut inconnu | `Invalid transition: PAID -> DELIVERED` |
| 404 | commande inexistante | `Order not found.` |

## 5. Annuler une commande

- **Méthode et route** : `POST /api/orders/{id}/cancel`
- **But** : annuler une commande `PENDING_PAYMENT` ou `PAID`. Le service interroge Shipping (refus si déjà expédiée), libère le stock chez Inventory, puis passe la commande à `CANCELLED`.
- **Paramètre d'URL** : `id` (string)
- **Corps** : aucun
- **Succès** : `200 OK`, objet Order avec `status = CANCELLED`

| Code | Cas | Message |
|---|---|---|
| 400 | statut ne permettant pas l'annulation | `This order cannot be cancelled.` |
| 400 | livraison déjà partie | `Cannot cancel an order that has already been shipped.` |
| 404 | commande inexistante | `Order not found.` |
| 503 | Shipping ou Inventory indisponible | `A dependent service is unavailable.` |

## 6. Vérifier l'état du service (route technique)

- **Méthode et route** : `GET /health`
- **But** : confirmer que le service est actif
- **Succès** : `200 OK`

```json
{ "status": "UP", "service": "order", "standalone": false }
```

---

## Dépendances (contrat attendu des autres services)

| Service | Appel fait par Order | Réponse attendue |
|---|---|---|
| Catalog (8082) | `GET /products/{id}` | `200` avec `{ "id", "name", "price" }` (`price` : nombre) ; `404` si inconnu |
| Inventory (8083) | `POST /api/inventory/reserve` avec `{ "items": [ { "productId", "quantity" } ] }` | `200`, ou `4xx` avec `{ "message" }` si stock insuffisant |
| Inventory (8083) | `POST /api/inventory/release` (même corps) | `200` |
| Shipping (8086) | `GET /api/shipments/order/{orderId}` | `200` avec un champ `status`, ou `404` s'il n'y a pas de livraison |