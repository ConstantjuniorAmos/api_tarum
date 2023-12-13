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

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == '__main__':
    app.run(port=int(os.environ.get('PORT', 5000)))
