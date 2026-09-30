# Inbound Receiving Reference Data & Schema

## Position in the Commerce Chain
```
┌─────────────────┐       ┌──────────────┐       ┌──────────────┐       ┌────────────────┐       ┌─────────────────┐
│  01 RECEIVING   │  ──▶  │   02 PREP    │  ──▶  │   03 PACK    │  ──▶  │   04 RETURNS   │  ──▶  │   05 RECOVERY   │
│  InspectIQ™     │       │  Compliance  │       │  Outbound    │       │  Disposition   │       │  Claims Engine  │
│ (Condition / PO)│       │  (FBA Route) │       │ (3PL Route)  │       │  & Damage Log  │       │ (Reconciles All)│
└─────────────────┘       └──────────────┘       └──────────────┘       └────────────────┘       └─────────────────┘
```

## Schema Reference

The CSV in `data/receiving_units_reference.csv` provides canonical sample records linking unit identifiers (`UNIT-0001` through `UNIT-0100`) across all 5 buildathon repositories:

| Column | Type | Description | Downstream Pod Consumers |
|---|---|---|---|
| `unit_id` | `String` | Unique Unit Identifier (`UNIT-0001` to `UNIT-0100`) | **All Pods (02, 03, 04, 05)** |
| `po_id` | `String` | Inbound Purchase Order ID | Pod 05 (Recovery Manager) |
| `supplier_id` | `String` | Manufacturer / Vendor code | Pod 05 (Supplier Chargeback) |
| `sku` | `String` | Stock Keeping Unit | Pod 02 (Prep) & Pod 03 (Pack) |
| `asin` | `String` | Amazon Standard Identification Number | Pod 02 (FBA Prep Item Barcode) |
| `fnsku` | `String` | Fulfillment Network Stock Keeping Unit | Pod 02 (FBA Item Labeling) |
| `expected_qty` | `Integer`| Ordered unit quantity per PO line | Pod 05 (Shortage calculations) |
| `received_qty` | `Integer`| Actual unit count observed by InspectIQ Vision Agent | Pod 05 (Dispute calculations) |
| `variant` | `String` | Color/Model variant observed | Pod 02 & Pod 03 |
| `carton_condition` | `Enum` | `INTACT`, `CRUSHED`, `WATER_DAMAGED`, `TORN`, `BLURRED`, `OCCLUDED`, `SEALED`, `TAMPERED` | Pod 02, 04, 05 |
| `unit_condition` | `Enum` | `INTACT`, `DAMAGED`, `MISSING_PARTS`, `UNKNOWN` | Pod 02, 04, 05 |
| `verdict` | `Enum` | `ACCEPT`, `EXCEPTION`, `UNCERTAIN`, `REJECT` | Pod 02 (Routing gate), Pod 05 |
| `route` | `Enum` | `FBA` (Amazon Fulfillment) or `3PL` (Merchant Packed) | Routes to Pod 02 or Pod 03 |
| `prep_required` | `Boolean`| Whether the unit can proceed to polybagging/labeling | Pod 02 (Prep Manager) |
| `claim_eligible`| `Boolean`| Whether a financial chargeback is automatically filed | Pod 05 (Recovery Manager) |
| `sha256_seal` | `Hex` | Cryptographic SHA-256 seal of the arrival evidence dossier | Pod 05 (Legal Dispute Proof) |

## Interoperability Handshake

1. **When `verdict == ACCEPT`**:
   - For `FBA` route $\rightarrow$ Transmitted to **02 Prep Manager** for polybagging, barcode scanning, and suffocation warning label validation.
   - For `3PL` route $\rightarrow$ Bypasses Prep and is staged directly for **03 Pack Manager**.

2. **When `verdict == EXCEPTION` or `REJECT`**:
   - Inspection dossier, photos, delta calculation, and SHA-256 hash are immediately packaged for **05 Recovery Manager** to file automated supplier chargebacks and carrier insurance claims.

3. **When `verdict == UNCERTAIN`**:
   - Receiving workflow is halted; dock operator is prompted with calibrated guidance (e.g., *"Photo blurred: Retake photo at minimum 1080p from 1.5m"* or *"Opaque carton: Spot unbox 1 master carton"*).
