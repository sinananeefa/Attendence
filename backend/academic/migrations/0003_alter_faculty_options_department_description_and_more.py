import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0002_initial'),
    ]

    operations = [

        # =========================================================
        # The following three changes were already applied before
        # the original 0003 failed:
        #
        #   Department.description
        #   Section.max_capacity
        #   Subject.is_elective
        #
        # We therefore represent them only in Django state.
        # =========================================================

        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterModelOptions(
                    name='faculty',
                    options={
                        'ordering': ['employee_id'],
                        'verbose_name_plural': 'Faculty',
                    },
                ),

                migrations.AddField(
                    model_name='department',
                    name='description',
                    field=models.TextField(
                        blank=True,
                        default='',
                    ),
                ),

                migrations.AddField(
                    model_name='section',
                    name='max_capacity',
                    field=models.PositiveSmallIntegerField(
                        default=60,
                    ),
                ),

                migrations.AddField(
                    model_name='subject',
                    name='is_elective',
                    field=models.BooleanField(
                        default=False,
                    ),
                ),
            ],
        ),

        # =========================================================
        # Subject.program
        # =========================================================

        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE academic_subject
                        ADD COLUMN program_id BIGINT NULL;
                    """,
                    reverse_sql="""
                        ALTER TABLE academic_subject
                        DROP COLUMN program_id;
                    """,
                ),

                migrations.RunSQL(
                    sql="""
                        ALTER TABLE academic_subject
                        ADD CONSTRAINT academic_subject_program_fk
                        FOREIGN KEY (program_id)
                        REFERENCES academic_program (id)
                        ON DELETE CASCADE;
                    """,
                    reverse_sql="""
                        ALTER TABLE academic_subject
                        DROP FOREIGN KEY academic_subject_program_fk;
                    """,
                ),
            ],

            state_operations=[
                migrations.AddField(
                    model_name='subject',
                    name='program',
                    field=models.ForeignKey(
                        blank=True,
                        help_text='Specific degree curriculum this subject is designed for',
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='subjects',
                        to='academic.program',
                    ),
                ),
            ],
        ),

        # =========================================================
        # AcademicClass
        # =========================================================

        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE academic_academicclass (
                            id BIGINT AUTO_INCREMENT NOT NULL PRIMARY KEY,
                            semester SMALLINT UNSIGNED NOT NULL,
                            academic_year_id BIGINT NOT NULL,
                            program_id BIGINT NOT NULL
                        );
                    """,
                    reverse_sql="""
                        DROP TABLE academic_academicclass;
                    """,
                ),

                migrations.RunSQL(
                    sql="""
                        ALTER TABLE academic_academicclass
                        ADD CONSTRAINT academic_academicclass_academic_year_fk
                        FOREIGN KEY (academic_year_id)
                        REFERENCES academic_academicyear (id)
                        ON DELETE CASCADE;
                    """,
                    reverse_sql="""
                        ALTER TABLE academic_academicclass
                        DROP FOREIGN KEY academic_academicclass_academic_year_fk;
                    """,
                ),

                migrations.RunSQL(
                    sql="""
                        ALTER TABLE academic_academicclass
                        ADD CONSTRAINT academic_academicclass_program_fk
                        FOREIGN KEY (program_id)
                        REFERENCES academic_program (id)
                        ON DELETE CASCADE;
                    """,
                    reverse_sql="""
                        ALTER TABLE academic_academicclass
                        DROP FOREIGN KEY academic_academicclass_program_fk;
                    """,
                ),

                migrations.RunSQL(
                    sql="""
                        ALTER TABLE academic_academicclass
                        ADD CONSTRAINT academic_academicclass_program_year_semester_uniq
                        UNIQUE (program_id, academic_year_id, semester);
                    """,
                    reverse_sql="""
                        ALTER TABLE academic_academicclass
                        DROP INDEX academic_academicclass_program_year_semester_uniq;
                    """,
                ),
            ],

            state_operations=[
                migrations.CreateModel(
                    name='AcademicClass',
                    fields=[
                        (
                            'id',
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name='ID',
                            ),
                        ),
                        (
                            'semester',
                            models.PositiveSmallIntegerField(
                                help_text='1 to 8',
                            ),
                        ),
                        (
                            'academic_year',
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='academic_classes',
                                to='academic.academicyear',
                            ),
                        ),
                        (
                            'program',
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='academic_classes',
                                to='academic.program',
                            ),
                        ),
                    ],
                    options={
                        'verbose_name_plural': 'Academic Classes',
                        'ordering': ['program', 'semester'],
                        'unique_together': {
                            ('program', 'academic_year', 'semester')
                        },
                    },
                ),
            ],
        ),

        # =========================================================
        # Section.academic_class
        # =========================================================

        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE academic_section
                        ADD COLUMN academic_class_id BIGINT NULL;
                    """,
                    reverse_sql="""
                        ALTER TABLE academic_section
                        DROP COLUMN academic_class_id;
                    """,
                ),

                migrations.RunSQL(
                    sql="""
                        ALTER TABLE academic_section
                        ADD CONSTRAINT academic_section_academic_class_fk
                        FOREIGN KEY (academic_class_id)
                        REFERENCES academic_academicclass (id)
                        ON DELETE SET NULL;
                    """,
                    reverse_sql="""
                        ALTER TABLE academic_section
                        DROP FOREIGN KEY academic_section_academic_class_fk;
                    """,
                ),
            ],

            state_operations=[
                migrations.AddField(
                    model_name='section',
                    name='academic_class',
                    field=models.ForeignKey(
                        blank=True,
                        help_text='Optional link to parent class cohort',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='sections',
                        to='academic.academicclass',
                    ),
                ),
            ],
        ),

        # =========================================================
        # CourseEnrollment
        # =========================================================

        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE academic_courseenrollment (
                            id BIGINT AUTO_INCREMENT NOT NULL PRIMARY KEY,
                            enrollment_date DATE NOT NULL,
                            is_active BOOL NOT NULL,
                            academic_year_id BIGINT NOT NULL,
                            section_id BIGINT NOT NULL,
                            student_id BIGINT NOT NULL,
                            subject_id BIGINT NOT NULL
                        );
                    """,
                    reverse_sql="""
                        DROP TABLE academic_courseenrollment;
                    """,
                ),

                migrations.RunSQL(
                    sql="""
                        ALTER TABLE academic_courseenrollment
                        ADD CONSTRAINT academic_courseenrollment_academic_year_fk
                        FOREIGN KEY (academic_year_id)
                        REFERENCES academic_academicyear (id)
                        ON DELETE CASCADE;
                    """,
                    reverse_sql="""
                        ALTER TABLE academic_courseenrollment
                        DROP FOREIGN KEY academic_courseenrollment_academic_year_fk;
                    """,
                ),

                migrations.RunSQL(
                    sql="""
                        ALTER TABLE academic_courseenrollment
                        ADD CONSTRAINT academic_courseenrollment_section_fk
                        FOREIGN KEY (section_id)
                        REFERENCES academic_section (id)
                        ON DELETE CASCADE;
                    """,
                    reverse_sql="""
                        ALTER TABLE academic_courseenrollment
                        DROP FOREIGN KEY academic_courseenrollment_section_fk;
                    """,
                ),

                migrations.RunSQL(
                    sql="""
                        ALTER TABLE academic_courseenrollment
                        ADD CONSTRAINT academic_courseenrollment_student_fk
                        FOREIGN KEY (student_id)
                        REFERENCES academic_student (id)
                        ON DELETE CASCADE;
                    """,
                    reverse_sql="""
                        ALTER TABLE academic_courseenrollment
                        DROP FOREIGN KEY academic_courseenrollment_student_fk;
                    """,
                ),

                migrations.RunSQL(
                    sql="""
                        ALTER TABLE academic_courseenrollment
                        ADD CONSTRAINT academic_courseenrollment_subject_fk
                        FOREIGN KEY (subject_id)
                        REFERENCES academic_subject (id)
                        ON DELETE CASCADE;
                    """,
                    reverse_sql="""
                        ALTER TABLE academic_courseenrollment
                        DROP FOREIGN KEY academic_courseenrollment_subject_fk;
                    """,
                ),

                migrations.RunSQL(
                    sql="""
                        ALTER TABLE academic_courseenrollment
                        ADD CONSTRAINT academic_courseenrollment_student_subject_year_uniq
                        UNIQUE (student_id, subject_id, academic_year_id);
                    """,
                    reverse_sql="""
                        DROP INDEX academic_courseenrollment_student_subject_year_uniq
                        ON academic_courseenrollment;
                    """,
                ),

                migrations.RunSQL(
                    sql="""
                        CREATE INDEX academic_co_student_481ee7_idx
                        ON academic_courseenrollment
                        (student_id, academic_year_id);
                    """,
                    reverse_sql="""
                        DROP INDEX academic_co_student_481ee7_idx
                        ON academic_courseenrollment;
                    """,
                ),

                migrations.RunSQL(
                    sql="""
                        CREATE INDEX academic_co_section_0358b0_idx
                        ON academic_courseenrollment
                        (section_id, subject_id);
                    """,
                    reverse_sql="""
                        DROP INDEX academic_co_section_0358b0_idx
                        ON academic_courseenrollment;
                    """,
                ),
            ],

            state_operations=[
                migrations.CreateModel(
                    name='CourseEnrollment',
                    fields=[
                        (
                            'id',
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name='ID',
                            ),
                        ),
                        (
                            'enrollment_date',
                            models.DateField(
                                auto_now_add=True,
                            ),
                        ),
                        (
                            'is_active',
                            models.BooleanField(
                                default=True,
                            ),
                        ),
                        (
                            'academic_year',
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='course_enrollments',
                                to='academic.academicyear',
                            ),
                        ),
                        (
                            'section',
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='course_enrollments',
                                to='academic.section',
                            ),
                        ),
                        (
                            'student',
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='course_enrollments',
                                to='academic.student',
                            ),
                        ),
                        (
                            'subject',
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='student_enrollments',
                                to='academic.subject',
                            ),
                        ),
                    ],
                    options={
                        'indexes': [
                            models.Index(
                                fields=['student', 'academic_year'],
                                name='academic_co_student_481ee7_idx',
                            ),
                            models.Index(
                                fields=['section', 'subject'],
                                name='academic_co_section_0358b0_idx',
                            ),
                        ],
                        'unique_together': {
                            ('student', 'subject', 'academic_year')
                        },
                    },
                ),
            ],
        ),

        # =========================================================
        # Semester
        # =========================================================

        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE academic_semester (
                            id BIGINT AUTO_INCREMENT NOT NULL PRIMARY KEY,
                            semester_number SMALLINT UNSIGNED NOT NULL,
                            term VARCHAR(10) NOT NULL,
                            start_date DATE NOT NULL,
                            end_date DATE NOT NULL,
                            is_active BOOL NOT NULL,
                            academic_year_id BIGINT NOT NULL
                        );
                    """,
                    reverse_sql="""
                        DROP TABLE academic_semester;
                    """,
                ),

                migrations.RunSQL(
                    sql="""
                        ALTER TABLE academic_semester
                        ADD CONSTRAINT academic_semester_academic_year_fk
                        FOREIGN KEY (academic_year_id)
                        REFERENCES academic_academicyear (id)
                        ON DELETE CASCADE;
                    """,
                    reverse_sql="""
                        ALTER TABLE academic_semester
                        DROP FOREIGN KEY academic_semester_academic_year_fk;
                    """,
                ),

                migrations.RunSQL(
                    sql="""
                        ALTER TABLE academic_semester
                        ADD CONSTRAINT academic_semester_academic_year_semester_uniq
                        UNIQUE (academic_year_id, semester_number);
                    """,
                    reverse_sql="""
                        DROP INDEX academic_semester_academic_year_semester_uniq
                        ON academic_semester;
                    """,
                ),
            ],

            state_operations=[
                migrations.CreateModel(
                    name='Semester',
                    fields=[
                        (
                            'id',
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name='ID',
                            ),
                        ),
                        (
                            'semester_number',
                            models.PositiveSmallIntegerField(
                                help_text='1 to 8',
                            ),
                        ),
                        (
                            'term',
                            models.CharField(
                                choices=[
                                    ('ODD', 'Odd Semester (Fall)'),
                                    ('EVEN', 'Even Semester (Spring)'),
                                ],
                                default='EVEN',
                                max_length=10,
                            ),
                        ),
                        (
                            'start_date',
                            models.DateField(),
                        ),
                        (
                            'end_date',
                            models.DateField(),
                        ),
                        (
                            'is_active',
                            models.BooleanField(default=True),
                        ),
                        (
                            'academic_year',
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='semesters',
                                to='academic.academicyear',
                            ),
                        ),
                    ],
                    options={
                        'ordering': [
                            'academic_year',
                            'semester_number',
                        ],
                        'unique_together': {
                            ('academic_year', 'semester_number')
                        },
                    },
                ),
            ],
        ),
    ]