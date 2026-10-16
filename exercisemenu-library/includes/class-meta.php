<?php
/**
 * Exercise and routine fields: registration, edit-screen boxes and saving.
 */

defined( 'ABSPATH' ) || exit;

class EM_Meta {

	/**
	 * Exercise fields. "lines" = one item per line, "slugs" = comma-separated exercise slugs.
	 */
	const EXERCISE_FIELDS = array(
		'_em_video_url'         => array( 'url', 'Demo video URL (MP4)', 'Optional. A looping MP4 loads far faster than a GIF. Leave empty to use the featured image (GIF).' ),
		'_em_gymvisual_id'      => array( 'text', 'Gym Visual ID', 'Number from the gymvisual.com product URL, e.g. 2691. Kept for licence records.' ),
		'_em_secondary_muscles' => array( 'text', 'Secondary muscles', 'Comma-separated, e.g. Obliques, Hip flexors' ),
		'_em_steps'             => array( 'lines', 'How to do it', 'One step per line.' ),
		'_em_cues'              => array( 'lines', 'Form cues', 'One cue per line.' ),
		'_em_mistakes'          => array( 'lines', 'Common mistakes', 'One mistake per line. Start with the mistake, then the fix after a colon.' ),
		'_em_easier'            => array( 'slug', 'Easier version (slug)', 'Exercise slug, e.g. medicine-ball-crunch' ),
		'_em_harder'            => array( 'slug', 'Harder version (slug)', 'Exercise slug' ),
		'_em_alternatives'      => array( 'slugs', 'Alternatives (slugs)', 'Comma-separated exercise slugs' ),
	);

	const ROUTINE_FIELDS = array(
		'_em_plan' => array( 'lines', 'Plan', '"# Day 1: Name" starts a day. Then one exercise per line: slug | sets | reps | rest seconds. Reps can be 10, 8-12, 10/side or 30s.' ),
	);

	/** Index flag shared by both post types. Unset = noindex and left out of sitemaps. */
	const INDEX_READY = '_em_index_ready';

	/** One row per exercise slug a routine uses, kept in sync with _em_plan. */
	const USES = '_em_uses';

	public static function init() {
		add_action( 'init', array( __CLASS__, 'register' ) );
		add_action( 'add_meta_boxes', array( __CLASS__, 'add_boxes' ) );
		add_action( 'save_post', array( __CLASS__, 'save_box' ), 10, 2 );
		add_action( 'added_post_meta', array( __CLASS__, 'plan_changed' ), 10, 4 );
		add_action( 'updated_post_meta', array( __CLASS__, 'plan_changed' ), 10, 4 );
		add_action( 'deleted_post_meta', array( __CLASS__, 'plan_deleted' ), 10, 3 );
	}

	public static function register() {
		$sets = array(
			EM_Post_Types::EXERCISE => self::EXERCISE_FIELDS,
			EM_Post_Types::ROUTINE  => self::ROUTINE_FIELDS,
		);
		foreach ( $sets as $post_type => $fields ) {
			foreach ( array_keys( $fields ) + array( 'ready' => self::INDEX_READY ) as $key ) {
				register_post_meta(
					$post_type,
					$key,
					array(
						'type'          => 'string',
						'single'        => true,
						'show_in_rest'  => true,
						'auth_callback' => function ( $allowed, $meta_key, $post_id ) {
							return current_user_can( 'edit_post', $post_id );
						},
					)
				);
			}
		}
	}

	public static function fields_for( $post_type ) {
		return EM_Post_Types::ROUTINE === $post_type ? self::ROUTINE_FIELDS : self::EXERCISE_FIELDS;
	}

	public static function add_boxes() {
		foreach ( array( EM_Post_Types::EXERCISE, EM_Post_Types::ROUTINE ) as $post_type ) {
			add_meta_box( 'em_fields', 'Exercise library details', array( __CLASS__, 'render_box' ), $post_type, 'normal', 'high' );
		}
	}

	public static function render_box( $post ) {
		wp_nonce_field( 'em_save_fields', 'em_fields_nonce' );

		echo '<table class="form-table" role="presentation">';
		foreach ( self::fields_for( $post->post_type ) as $key => $field ) {
			list( $type, $label, $help ) = $field;
			$value                       = get_post_meta( $post->ID, $key, true );
			$id                          = esc_attr( ltrim( $key, '_' ) );

			echo '<tr><th scope="row"><label for="' . $id . '">' . esc_html( $label ) . '</label></th><td>';
			if ( 'lines' === $type ) {
				$rows = '_em_plan' === $key ? 16 : 5;
				printf( '<textarea id="%1$s" name="em[%2$s]" rows="%3$d" class="large-text code">%4$s</textarea>', $id, esc_attr( $key ), $rows, esc_textarea( $value ) );
			} else {
				printf( '<input type="text" id="%1$s" name="em[%2$s]" value="%3$s" class="regular-text">', $id, esc_attr( $key ), esc_attr( $value ) );
			}
			echo '<p class="description">' . esc_html( $help ) . '</p>';

			if ( '_em_plan' === $key && '' !== $value ) {
				self::render_plan_check( $value );
			}
			echo '</td></tr>';
		}

		printf(
			'<tr><th scope="row">Search engines</th><td><label><input type="checkbox" name="em[%1$s]" value="1"%2$s> Ready to index</label><p class="description">Leave unticked until the page is reviewed and has its demo media. Unticked pages are noindex and stay out of the sitemap.</p></td></tr>',
			esc_attr( self::INDEX_READY ),
			checked( get_post_meta( $post->ID, self::INDEX_READY, true ), '1', false )
		);
		echo '</table>';
	}

	/** Shows plan errors and exercises the plan names that do not exist yet. */
	private static function render_plan_check( $plan_text ) {
		$plan    = EM_Routine_Plan::parse( $plan_text );
		$missing = array();
		foreach ( EM_Routine_Plan::slugs( $plan['days'] ) as $slug ) {
			if ( ! EM_Render::exercise_by_slug( $slug, array( 'publish', 'draft', 'pending', 'future' ) ) ) {
				$missing[] = $slug;
			}
		}

		foreach ( $plan['errors'] as $error ) {
			echo '<p style="color:#b32d2e">' . esc_html( $error ) . '</p>';
		}
		if ( $missing ) {
			echo '<p style="color:#b32d2e">No exercise with these slugs: ' . esc_html( implode( ', ', $missing ) ) . '. They show as plain text until the exercise exists.</p>';
		}

		$summary = EM_Routine_Plan::summary( $plan['days'] );
		printf(
			'<p><strong>Calculated:</strong> %d days, %d exercises, about %s min per session.</p>',
			(int) $summary['days'],
			(int) $summary['exercises'],
			esc_html( EM_Render::minutes_label( $summary ) )
		);
	}

	public static function save_box( $post_id, $post ) {
		if ( ! isset( $_POST['em_fields_nonce'] ) || ! wp_verify_nonce( sanitize_key( $_POST['em_fields_nonce'] ), 'em_save_fields' ) ) {
			return;
		}
		if ( ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) || wp_is_post_revision( $post_id ) || ! current_user_can( 'edit_post', $post_id ) ) {
			return;
		}

		$input = isset( $_POST['em'] ) && is_array( $_POST['em'] ) ? wp_unslash( $_POST['em'] ) : array();
		$input[ self::INDEX_READY ] = empty( $input[ self::INDEX_READY ] ) ? '' : '1';

		self::save_fields( $post_id, $post->post_type, $input );
	}

	/**
	 * Sanitises and stores fields. Used by the edit screen and the importer.
	 * Keys missing from $values are left untouched.
	 */
	public static function save_fields( $post_id, $post_type, array $values ) {
		$fields                      = self::fields_for( $post_type );
		$fields[ self::INDEX_READY ] = array( 'flag' );

		foreach ( $fields as $key => $field ) {
			if ( ! array_key_exists( $key, $values ) ) {
				continue;
			}
			$value = self::sanitize( $field[0], $values[ $key ] );
			if ( '' === $value ) {
				delete_post_meta( $post_id, $key );
			} else {
				update_post_meta( $post_id, $key, $value );
			}
		}
	}

	private static function sanitize( $type, $value ) {
		if ( is_array( $value ) ) {
			$value = 'slugs' === $type ? implode( ',', $value ) : implode( "\n", $value );
		}
		$value = (string) $value;

		switch ( $type ) {
			case 'url':
				return esc_url_raw( trim( $value ) );
			case 'slug':
				return sanitize_title( $value );
			case 'slugs':
				return implode( ',', array_filter( array_map( 'sanitize_title', explode( ',', $value ) ) ) );
			case 'lines':
				return trim( sanitize_textarea_field( $value ) );
			case 'flag':
				return $value ? '1' : '';
			default:
				return sanitize_text_field( $value );
		}
	}

	/** Keeps the _em_uses rows in step with the routine plan, however the plan was saved. */
	public static function plan_changed( $meta_id, $post_id, $meta_key, $meta_value ) {
		if ( '_em_plan' !== $meta_key ) {
			return;
		}
		$plan = EM_Routine_Plan::parse( $meta_value );
		delete_post_meta( $post_id, self::USES );
		foreach ( EM_Routine_Plan::slugs( $plan['days'] ) as $slug ) {
			add_post_meta( $post_id, self::USES, $slug );
		}
	}

	public static function plan_deleted( $meta_ids, $post_id, $meta_key ) {
		if ( '_em_plan' === $meta_key ) {
			delete_post_meta( $post_id, self::USES );
		}
	}

	/** Splits a "lines" field into non-empty items. */
	public static function lines( $post_id, $key ) {
		$value = (string) get_post_meta( $post_id, $key, true );
		return array_values( array_filter( array_map( 'trim', preg_split( '/\r\n|\r|\n/', $value ) ) ) );
	}

	/** Splits a "slugs" field. */
	public static function slugs( $post_id, $key ) {
		$value = (string) get_post_meta( $post_id, $key, true );
		return array_values( array_filter( array_map( 'trim', explode( ',', $value ) ) ) );
	}
}
