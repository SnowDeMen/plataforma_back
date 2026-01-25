"""
Mapeos Airtable -> Postgres por tabla.

Este es el punto recomendado para que tengas “control total” sobre:
- qué columnas existen en Postgres
- cómo se transforman los valores de Airtable
- cómo se resuelven relaciones (FKs) cuando Airtable usa links

Patrón sugerido:
- Mantén el DDL en `schema.sql` alineado con estas definiciones.
- Define una función por tabla (o un diccionario) y selecciónala por AIRTABLE_TABLE_NAME.
"""

from __future__ import annotations

from .sync_config import TableSyncConfig
from .types import FieldMapping


def get_table_sync_config(
    *,
    airtable_table_name: str,
    airtable_last_modified_field: str,
    target_schema: str = "airtable",
    target_table: str | None = None,
) -> TableSyncConfig:
    """
    Retorna la configuración de sync para la tabla indicada.

    IMPORTANTE:
    - Edita este archivo para reflejar tu modelado real.
    - Si quieres modelado relacional, crea múltiples tablas y múltiples configs.
    """
    if not target_table:
        # Por defecto, usamos el nombre de tabla Airtable normalizado a snake_case simple.
        # Si tu tabla contiene espacios, se reemplazan por '_'.
        target_table = airtable_table_name.strip().lower().replace(" ", "_")

    if airtable_table_name == "Athletes":
        return TableSyncConfig(
            airtable_table_name=airtable_table_name,
            airtable_last_modified_field=airtable_last_modified_field,
            target_schema=target_schema,
            target_table="athletes",
            field_mappings=[
                FieldMapping(airtable_field="Name", pg_column="name", required=True),
                FieldMapping(airtable_field="Status", pg_column="status"),
                FieldMapping(airtable_field="Discipline", pg_column="discipline"),
                FieldMapping(airtable_field="Level", pg_column="level"),
                FieldMapping(airtable_field="Goal", pg_column="goal"),
                FieldMapping(airtable_field="Age", pg_column="age", transform=lambda v: int(v) if v else None),
                FieldMapping(airtable_field="Experience", pg_column="experience"),
                # JSON Fields - Flattened in Airtable, structured in DB
                FieldMapping(
                    airtable_field="Gender", 
                    pg_column="personal", 
                    transform=lambda v: {"genero": v} if v else {}
                ),
            ],
            external_id_column="airtable_id", # Use generic ID column
        )

    # Match case-insensitively to handle user typos (e.g. Formulario_inicial vs Formulario_Inicial)
    if airtable_table_name.lower() == "formulario_inicial":
        # Force the canonical name for the API call
        canonical_name = "Formulario_Inicial"
        
        return TableSyncConfig(
            airtable_table_name=canonical_name,
            airtable_last_modified_field=airtable_last_modified_field,
            target_schema="public",
            target_table="athletes",
            field_mappings=[
                FieldMapping(airtable_field="Nombre(s)", pg_column="full_name"),
                FieldMapping(
                    airtable_field="Apellido(s)", 
                    pg_column="last_name",
                    transform=lambda v: str(v).strip().title() if v else None
                ),
                FieldMapping(airtable_field="Consentimiento", pg_column="consent"),
                FieldMapping(airtable_field="Fecha de nacimiento", pg_column="date_of_birth"),
                FieldMapping(airtable_field="Género", pg_column="gender"),
                FieldMapping(airtable_field="País", pg_column="country"),
                FieldMapping(airtable_field="Estado", pg_column="state"),
                FieldMapping(airtable_field="Ciudad", pg_column="city"),
                FieldMapping(airtable_field="Instagram", pg_column="instagram"),
                FieldMapping(airtable_field="Contacto de emergencia", pg_column="emergency_contact_name"),
                FieldMapping(airtable_field="Teléfono contacto de emergencia", pg_column="emergency_contact_phone"),
                FieldMapping(airtable_field="Peso actual", pg_column="current_weight", transform=lambda v: str(v) if v else None),
                FieldMapping(airtable_field="Peso objetivo", pg_column="target_weight", transform=lambda v: str(v) if v else None),
                FieldMapping(airtable_field="Peso Máximo Histórico", pg_column="max_historical_weight", transform=lambda v: str(v) if v else None),
                FieldMapping(airtable_field="Altura", pg_column="height", transform=lambda v: str(v) if v else None),
                FieldMapping(airtable_field="Enfermedad o padecimientos", pg_column="diseases_conditions"),
                FieldMapping(airtable_field="Lesión o enfermedad aguda", pg_column="acute_injury_disease"),
                FieldMapping(airtable_field="Tipo de lesión o enfermedad aguda", pg_column="acute_injury_type"),
                FieldMapping(airtable_field="¿Te has fracturado o esguinzado previamente?", pg_column="has_fractures_sprains_history"),
                FieldMapping(airtable_field="Historial de Fracturas", pg_column="fracture_history"),
                FieldMapping(airtable_field="Medicamentos", pg_column="medications"),
                FieldMapping(airtable_field="Suplementos", pg_column="supplements"),
                FieldMapping(
                    airtable_field="¿Fumas?", 
                    pg_column="smoker",
                    transform=lambda v: ", ".join(v) if isinstance(v, list) else str(v) if v else None
                ),
                FieldMapping(
                    airtable_field="Alcohol", 
                    pg_column="alcohol_consumption",
                    transform=lambda v: ", ".join(v) if isinstance(v, list) else str(v) if v else None
                ),
                FieldMapping(airtable_field="¿Cuántas horas al día duermes?", pg_column="daily_sleep_hours"),
                FieldMapping(airtable_field="¿Cómo calificas tu calidad de sueño?", pg_column="sleep_quality"),
                FieldMapping(airtable_field="Comidas al día", pg_column="meals_per_day"),
                FieldMapping(airtable_field="Dieta", pg_column="diet_type"),
                FieldMapping(airtable_field="Cuentame un poco sobre tu dieta", pg_column="diet_description"),
                FieldMapping(airtable_field="Tipo de atleta", pg_column="athlete_type"),
                FieldMapping(airtable_field="Tipo de atleta", pg_column="level"),
                FieldMapping(
                    airtable_field="¿Cuántas disciplinas vas a practicar?", 
                    pg_column="discipline",
                    transform=lambda v: ", ".join(v) if isinstance(v, list) else str(v) if v else None
                ),
                FieldMapping(airtable_field="¿Qué deportes has practicado previamente?", pg_column="previous_sports"),
                FieldMapping(airtable_field="Tiempo practicando Running", pg_column="running_experience_time"),
                FieldMapping(airtable_field="Tiempo practicando Ciclismo", pg_column="cycling_experience_time"),
                FieldMapping(airtable_field="Tiempo practicando Natación", pg_column="swimming_experience_time"),
                FieldMapping(airtable_field="¿Cuál es tu objetivo a corto plazo?", pg_column="short_term_goal"),
                FieldMapping(airtable_field="¿Cuál es tu objetivo a mediano plazo?", pg_column="medium_term_goal"),
                FieldMapping(airtable_field="¿Cuál es tu objetivo a largo plazo?", pg_column="long_term_goal"),
                FieldMapping(airtable_field="Mejor tiempo en un 5k", pg_column="best_time_5k"),
                FieldMapping(airtable_field="Mejor tiempo en un 10k", pg_column="best_time_10k"),
                FieldMapping(airtable_field="Mejor tiempo en un 21k", pg_column="best_time_21k"),
                FieldMapping(airtable_field="Maratón", pg_column="marathon_time"),
                FieldMapping(airtable_field="Triatlón", pg_column="triathlon_distance"),
                FieldMapping(airtable_field="Tiempo logrado en el triatlón", pg_column="triathlon_time"),
                FieldMapping(airtable_field="Lugar Triatlón", pg_column="triathlon_place"),
                FieldMapping(airtable_field="¿Distancia más larga que has corrido (aprox)?", pg_column="longest_run_distance"),
                FieldMapping(airtable_field="¿En qué fué?", pg_column="longest_run_event"),
                FieldMapping(airtable_field="¿Cuándo fue?", pg_column="longest_run_date"),
                FieldMapping(airtable_field="¿Cuántas veces a la semana entrenas?", pg_column="training_frequency_weekly"),
                FieldMapping(airtable_field="¿Cuántas horas a la semana le dedicas al deporte que practicas?", pg_column="training_hours_weekly"),
                FieldMapping(airtable_field="Horario Preferido", pg_column="preferred_schedule"),
                FieldMapping(airtable_field="Horario", pg_column="schedule"),
                FieldMapping(airtable_field="Día preferido de descanso", pg_column="preferred_rest_day"),
                FieldMapping(airtable_field="¿Estarías de acuerdo en sacrificar ese día de descanso por uno de regeneración activa?", pg_column="sacrifice_rest_day"),
                FieldMapping(airtable_field="¿Cuál es tu evento principal?", pg_column="main_event"),
                FieldMapping(airtable_field="Tipo de evento", pg_column="event_type"),
                FieldMapping(airtable_field="¿En cuánto tiempo es?", pg_column="time_to_event"),
                FieldMapping(airtable_field="¿Tienes planeados eventos secundarios o de preparación?", pg_column="secondary_events"),
                FieldMapping(airtable_field="¿Cuentas con reloj? ¿Qué marca?", pg_column="watch_brand_model"),
                FieldMapping(airtable_field="¿Cuentas con reloj?", pg_column="has_watch"),
                FieldMapping(airtable_field="¿Qué marca de reloj?", pg_column="watch_brand"),
                FieldMapping(
                    airtable_field="¿Con cuál de los siguientes medidores cuentas?", 
                    pg_column="sensors_owned",
                     transform=lambda v: ", ".join(v) if isinstance(v, list) else str(v) if v else None
                ),
                FieldMapping(airtable_field="¿Cuentas con alberca?", pg_column="has_pool_access"),
                FieldMapping(airtable_field="¿Cuentas con rodillo inteligente?", pg_column="has_smart_trainer"),
                FieldMapping(airtable_field="Escribe una breve explicación de por qué quieres practicar el deporte", pg_column="reason_for_sport"),
                FieldMapping(airtable_field="Platícame tus metas deportivas para este año", pg_column="annual_goals"),
                FieldMapping(airtable_field="Canales preferidos de comunicación", pg_column="preferred_communication_channels"),
                FieldMapping(airtable_field="¿Tienes interés en unirte a grupos de WhatsApp?", pg_column="whatsapp_group_interest"),
                FieldMapping(airtable_field="Descuento", pg_column="discount"),
                FieldMapping(airtable_field="Cliente", pg_column="client_status"),
                FieldMapping(airtable_field="Fecha de registro antigua", pg_column="old_registration_date"),
                FieldMapping(airtable_field="Pago pendiente", pg_column="pending_payment"),
                FieldMapping(airtable_field="Link de formulario (from Cliente)", pg_column="form_link"),
                FieldMapping(airtable_field="Categoria Objetivo Peso", pg_column="weight_objective_category"),
                FieldMapping(airtable_field="% Malos Habitos", pg_column="bad_habits_percentage", transform=lambda v: str(v) if v else None),
                FieldMapping(airtable_field="Fecha de Registro", pg_column="registration_date"),
                FieldMapping(airtable_field="Fecha de inicio de entrenamiento", pg_column="training_start_date"),
                FieldMapping(airtable_field="Estatus", pg_column="status"),
                # TrainingPeaks Integration
                FieldMapping(airtable_field="Cuenta TrainingPeaks", pg_column="tp_username"),
                # Mapeos adicionales para unificar
                FieldMapping(
                    airtable_field="Nombre(s)", 
                    pg_column="name", 
                    required=True,
                    transform=lambda v: str(v).strip().title() if v else None
                ), # Usamos Nombre completo como fallback para 'name'
            ],
            external_id_column="airtable_id",
            record_id_column="id",
        )

    # ---------------------------------------------------------------------
    # EJEMPLO: reemplaza esto por tu tabla real
    # ---------------------------------------------------------------------
    # Si NO quieres hardcodear por nombre, puedes simplemente devolver
    # un mapeo genérico para 1 tabla (tu caso actual).
    return TableSyncConfig(
        airtable_table_name=airtable_table_name,
        airtable_last_modified_field=airtable_last_modified_field,
        target_schema=target_schema,
        target_table=target_table,
        field_mappings=[
            # TODO: Cambia "Nombre", "Email", "Edad" por tus fields reales.
            FieldMapping(airtable_field="Nombre", pg_column="name", required=True),
            FieldMapping(airtable_field="Email", pg_column="email"),
            FieldMapping(
                airtable_field="Edad",
                pg_column="age",
                transform=lambda v: int(v) if v is not None else None,
            ),
        ],
        external_id_column=None,
    )
