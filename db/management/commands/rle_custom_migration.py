from django.core.management import BaseCommand
from django.db import connection


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--datasets",
            "-ds",
            nargs="+",
            help="List of dataset names to selectively update RLE for (instead of full rebuild)",
        )

    def handle(self, *args, **options):
        datasets = options.get("datasets", None)

        with connection.cursor() as cursor:
            if datasets:
                self._selective_rle(cursor, datasets)
            else:
                self._full_rle(cursor)

    def _full_rle(self, cursor):
        print("Applying RLE (full rebuild)...")
        cursor.execute(
            """
    DROP TABLE IF EXISTS aoi_timepoints_indexed;
    DROP TABLE IF EXISTS aoi_timepoints_rle;
    create table aoi_timepoints_indexed as
    select aoi_timepoints.*,
            (row_number() over (partition by administration_id, trial_id order by t_norm) -
             row_number() over (partition by administration_id, trial_id, aoi order by t_norm)
            ) as grp
    from aoi_timepoints;
    CREATE INDEX idx_administration_trial_aoi_grp ON aoi_timepoints_indexed (administration_id, trial_id, aoi, grp);
    create table aoi_timepoints_rle as
    select administration_id, trial_id, min(t_norm) as t_norm, aoi, count(*) as length
    from aoi_timepoints_indexed
    group by administration_id, trial_id, aoi, grp
    order by administration_id, trial_id, t_norm;
                """
        )

    def _selective_rle(self, cursor, dataset_names):
        print(f"Applying RLE (selective update for datasets: {', '.join(dataset_names)})...")

        # Check if aoi_timepoints_rle exists; if not, fall back to full rebuild
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = 'aoi_timepoints_rle'"
        )
        if cursor.fetchone()[0] == 0:
            print("aoi_timepoints_rle table does not exist, falling back to full rebuild...")
            self._full_rle(cursor)
            return

        placeholders = ",".join(["%s"] * len(dataset_names))

        # Delete existing RLE rows for the specified datasets
        cursor.execute(
            f"""
            DELETE aoi_timepoints_rle FROM aoi_timepoints_rle
            INNER JOIN administrations ON aoi_timepoints_rle.administration_id = administrations.administration_id
            INNER JOIN datasets ON administrations.dataset_id = datasets.dataset_id
            WHERE datasets.dataset_name IN ({placeholders})
            """,
            dataset_names,
        )

        # Insert new RLE rows for the specified datasets using a CTE
        cursor.execute(
            f"""
            INSERT INTO aoi_timepoints_rle (administration_id, trial_id, t_norm, aoi, length)
            WITH filtered AS (
                SELECT aoi_timepoints.administration_id,
                       aoi_timepoints.trial_id,
                       aoi_timepoints.t_norm,
                       aoi_timepoints.aoi,
                       (ROW_NUMBER() OVER (PARTITION BY aoi_timepoints.administration_id, aoi_timepoints.trial_id ORDER BY aoi_timepoints.t_norm) -
                        ROW_NUMBER() OVER (PARTITION BY aoi_timepoints.administration_id, aoi_timepoints.trial_id, aoi_timepoints.aoi ORDER BY aoi_timepoints.t_norm)
                       ) AS grp
                FROM aoi_timepoints
                INNER JOIN administrations ON aoi_timepoints.administration_id = administrations.administration_id
                INNER JOIN datasets ON administrations.dataset_id = datasets.dataset_id
                WHERE datasets.dataset_name IN ({placeholders})
            )
            SELECT administration_id, trial_id, MIN(t_norm) AS t_norm, aoi, COUNT(*) AS length
            FROM filtered
            GROUP BY administration_id, trial_id, aoi, grp
            ORDER BY administration_id, trial_id, t_norm
            """,
            dataset_names,
        )
