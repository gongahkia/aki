use crate::ui::widgets::checkbox::CheckboxItem;

/// 28 Singapore tort law topics in 6 categories -- compiled into binary
pub fn topic_items() -> Vec<CheckboxItem> {
    vec![
        CheckboxItem::header("Negligence-Based"),
        CheckboxItem::option(
            "Negligence",
            "negligence",
            "duty, breach, damage, causation",
        ),
        CheckboxItem::option(
            "Duty Of Care",
            "duty_of_care",
            "neighbour principle, proximity",
        ),
        CheckboxItem::option(
            "Standard Of Care",
            "standard_of_care",
            "reasonable person standard",
        ),
        CheckboxItem::option("Causation", "causation", "but-for test, legal causation"),
        CheckboxItem::option("Remoteness", "remoteness", "foreseeability of damage"),
        CheckboxItem::option(
            "Contributory Negligence",
            "contributory_negligence",
            "claimant's own fault",
        ),
        CheckboxItem::header("Intentional Torts"),
        CheckboxItem::option("Battery", "battery", "intentional application of force"),
        CheckboxItem::option("Assault", "assault", "apprehension of immediate contact"),
        CheckboxItem::option(
            "False Imprisonment",
            "false_imprisonment",
            "unlawful restraint of liberty",
        ),
        CheckboxItem::option(
            "Trespass To Land",
            "trespass_to_land",
            "unlawful entry onto land",
        ),
        CheckboxItem::header("Liability"),
        CheckboxItem::option(
            "Vicarious Liability",
            "vicarious_liability",
            "employer liability for employee torts",
        ),
        CheckboxItem::option(
            "Strict Liability",
            "strict_liability",
            "liability without fault",
        ),
        CheckboxItem::option(
            "Occupiers Liability",
            "occupiers_liability",
            "duties to visitors and trespassers",
        ),
        CheckboxItem::option(
            "Employers Liability",
            "employers_liability",
            "workplace safety duties",
        ),
        CheckboxItem::option(
            "Product Liability",
            "product_liability",
            "defective product claims",
        ),
        CheckboxItem::header("Specific Torts"),
        CheckboxItem::option(
            "Defamation",
            "defamation",
            "false statements harming reputation",
        ),
        CheckboxItem::option(
            "Private Nuisance",
            "private_nuisance",
            "unreasonable interference with land use",
        ),
        CheckboxItem::option(
            "Harassment",
            "harassment",
            "course of conduct causing alarm",
        ),
        CheckboxItem::header("Damages"),
        CheckboxItem::option(
            "Economic Loss",
            "economic_loss",
            "pure financial loss claims",
        ),
        CheckboxItem::option(
            "Psychiatric Harm",
            "psychiatric_harm",
            "nervous shock and mental injury",
        ),
        CheckboxItem::header("Doctrines & Defences"),
        CheckboxItem::option(
            "Breach Of Statutory Duty",
            "breach_of_statutory_duty",
            "breach of obligations imposed by statute",
        ),
        CheckboxItem::option(
            "Rylands V Fletcher",
            "rylands_v_fletcher",
            "strict liability for escape of dangerous things",
        ),
        CheckboxItem::option(
            "Consent Defence",
            "consent_defence",
            "voluntary assumption of known risk",
        ),
        CheckboxItem::option(
            "Illegality Defence",
            "illegality_defence",
            "claim barred by claimant illegality",
        ),
        CheckboxItem::option(
            "Limitation Periods",
            "limitation_periods",
            "time-bar and accrual limits",
        ),
        CheckboxItem::option(
            "Res Ipsa Loquitur",
            "res_ipsa_loquitur",
            "inference of negligence from circumstances",
        ),
        CheckboxItem::option(
            "Novus Actus Interveniens",
            "novus_actus_interveniens",
            "intervening act breaks causation chain",
        ),
        CheckboxItem::option(
            "Volenti Non Fit Injuria",
            "volenti_non_fit_injuria",
            "no injury where risk was voluntarily accepted",
        ),
    ]
}
