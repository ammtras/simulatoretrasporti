from decimal import Decimal


class DetailRendererService:

    @staticmethod
    def render(d: dict):
        """
        Converte qualsiasi dettaglio annidato in lista piatta UI-safe
        """

        if not d:
            return []

        items = []

        def walk(prefix, obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    label = f"{prefix}{k}".replace("_", " ").capitalize()
                    walk(label + ": ", v)

            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    walk(f"{prefix}{i} ", v)

            else:
                # Sostituito 'v' con 'obj'
                if DetailRendererService._is_valid(v=obj):
                    items.append({
                        "label": prefix.strip(": "),
                        "value": obj  # <--- FIX QUI: prima era 'v'
                    })

        walk("", d)

        return items

    @staticmethod

    @staticmethod
    def _is_valid(v):
        if v is None:
            return False

        # 🔴 NUOVO FILTRO: Se il valore è un numero (int, float o Decimal)
        # e il suo valore assoluto è inferiore a 0.01, lo escludiamo.
        if isinstance(v, (int, float, Decimal)):
            if abs(v) < Decimal("0.01"):
                return False

        # Rimangono validi i controlli precedenti per le stringhe vuote
        if isinstance(v, str) and v.strip() == "":
            return False

        return True