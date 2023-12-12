import flask
from flask import request, jsonify, render_template
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime  # Ajoutez cette ligne pour obtenir la date et l'heure actuelles
import os 
from dotenv import load_dotenv
import stripe

load_dotenv()
app = flask.Flask(__name__)

# Configuration de Firebase
cred = credentials.Certificate("./creditials.json")  # Remplacez par le chemin correct
firebase_admin.initialize_app(cred)
db = firestore.client()

# Configuration de Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
# Fonction de création d'un paiement
def create_payment(amount, currency, customer_id, token):
    # Création d'un objet de paiement Stripe
    payment = stripe.PaymentIntent.create(
        amount=amount,
        currency=currency,
        customer=customer_id,
        payment_method=token
    )

    # Vérification de l'état du paiement
    if payment.status == "succeeded":
        # Paiement réussi
        return payment
    else:
        # Paiement échoué
        return None

# Fonction de virement d'un paiement avec données bancaires
def transfer_payment(amount, bank_info):
    # Création d'un objet de virement Stripe
    transfer = stripe.Transfer.create(
        amount=amount,
        currency=bank_info["currency"],
        destination=bank_info
    )

    # Vérification de l'état du virement
    if transfer.status == "succeeded":
        # Virement réussi
        return transfer
    else:
        # Virement échoué
        return None

# Fonction de remboursement d'un paiement
def refund_payment(payment_id, amount):
    # Création d'un objet de remboursement Stripe
    refund = stripe.Refund.create(
        payment_intent=payment_id,
        amount=amount
    )

    # Vérification de l'état du remboursement
    if refund.status == "succeeded":
        # Remboursement réussi
        return refund
    else:
        # Remboursement échoué
        return None

# Fonction de création d'un payment_method
def create_payment_method(card_number, exp_month, exp_year, cvc):
    # Création d'un objet de payment_method Stripe
    payment_method = stripe.PaymentMethod.create(
        card={
            "number": card_number,
            "exp_month": exp_month,
            "exp_year": exp_year,
            "cvc": cvc,
        },
    )

    # Retourne l'ID du payment_method
    return payment_method.id


def get_stripe_activities():
    # Récupération de toutes les activités de paiement
    activities = stripe.PaymentIntent.list(limit=100)

    # Parcours des activités de paiement
    for activity in activities.data:
        # Création d'un objet d'activité pour Firebase
        activity_data = {
            "id": activity.id,
            "amount": activity.amount,
            "currency": activity.currency,
            "status": activity.status,
            "type": activity.type,
        }

        # Envoi de l'objet d'activité sur Firebase
        db.collection("activities").document(activity.id).set(activity_data)

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

# Point d'entrée de l'API pour la création de paiements
@app.route("/payments", methods=["POST"])
def payments():
    try:
        # Récupération des données de la requête
        amount = request.json["amount"]
        currency = request.json["currency"]
        customer_id = 'acct_1GkdzFBCqDheBpUE'


        # Récupération des informations du client depuis Firebase
        uid = request.json["uid"]
        client = db.collection("clients").document(uid).get()


        # Création du payment_method en récupérant les données du client
        payment_method_id = create_payment_method(
            card_number=client.get("card_number"),
            exp_month=client.get("exp_month"),
            exp_year=client.get("exp_year"),
            cvc=client.get("cvv")
        )


        # Création du paiement en utilisant le payment_method créé
        payment = create_payment(amount, currency, customer_id, payment_method_id)


        # Enregistrement des informations du paiement dans Firebase
        if payment:
            payment_data = {
                "payment_id": payment.id,
                "amount": amount,
                "currency": currency,
                "customer_id": customer_id,
                "statut": payment.status,
                'type': "prevelement",
                "payment_method_id": payment_method_id,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }


            # Ajout de l'enregistrement à la collection "payments" dans Firebase
            db.collection("payments").add(payment_data)

            return jsonify({"message": "Payment successful"})
        else:
            return jsonify({"error": "Payment failed"})
    except Exception as e:
        return jsonify({"error": str(e)})
    

# Point d'entrée de l'API pour les transferts
@app.route("/transfers", methods=["POST"])
def transfers():
    try:
        # Récupération des données de la requête
        amount = request.json["amount"]

        # Récupération des informations du virement du transporteur depuis la requête
        document_id = request.json["document_id"]
        payments_id = request.json["payments_id"]
        bankInfoUser = db.collection("bankInfo").document(document_id).get()

        # Création des informations du compte bancaire à partir des données récupérées
        bank_info = {
            "type": "iban",
            "currency": "EUR",  # Remplacez par la devise appropriée
            "account_holder_name": bankInfoUser["Name"],
            "iban": bankInfoUser["IbanUser"]
        }

        # Appel de la fonction de transfert avec les informations du compte bancaire
        resultat_transfert = transfer_payment(amount, bank_info)

        # Vérification du résultat du transfert
        if resultat_transfert:
            resultat_transfert_ = {
                "payment_id_transfer": resultat_transfert.id,
                "amount_transfert": amount,
                "type": "virement",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            # Ajout de l'enregistrement à la collection "payments" dans Firebase
            db.collection("payments").document(payments_id).update(resultat_transfert_)

            return jsonify({"message": "Transfert successful"})
        else:
            return jsonify({"error": "Transfer failed"})
    except Exception as e:
        return jsonify({"error": str(e)})

# Point d'entrée de l'API pour les remboursements
@app.route("/refunds", methods=["POST"])
def refunds():
    # Récupération des données de la requête
    payment_id = request.json["payment_id"]
    amount = request.json["amount"]

    # Appel de la fonction de remboursement avec les informations du paiement
    resultat_remboursement = refund_payment(payment_id, amount)

    # Vérification du résultat du remboursement
    if resultat_remboursement:
        return jsonify(resultat_remboursement)
    else:
        return jsonify({"error":"Refund failed"})

@app.route("/sync_stripe_activities", methods=["GET"])
def sync_stripe_activities():
    try:
        # Appel de la fonction pour récupérer les activités de Stripe
        get_stripe_activities()
        return jsonify({"message": "Sync completed successfully"})
    except Exception as e:
        return jsonify({"error": str(e)})


if __name__ == '__main__':
    app.run(debug=True)
