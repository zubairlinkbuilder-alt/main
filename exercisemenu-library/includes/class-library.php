<?php
/**
 * [em_exercise_library] and [em_routine_library]: filterable grids for the
 * /exercises/ and /workout-routines/ pages.
 *
 * Filters use f_* parameters, not the taxonomy query vars: ?muscle=chest on a
 * Page would turn the main query into a taxonomy archive and lose the page.
 */

defined( 'ABSPATH' ) || exit;

class EM_Library {

	const PER_PAGE = 24;

	public static function init() {
		add_shortcode( 'em_exercise_library', array( __CLASS__, 'exercises' ) );
		add_shortcode( 'em_routine_library', array( __CLASS__, 'routines' ) );
	}

	public static function exercises() {
		$filters = array(
			'em_muscle'    => 'Muscle',
			'em_equipment' => 'Equipment',
			'em_level'     => 'Level',
		);
		return self::library( EM_Post_Types::EXERCISE, $filters, array( __CLASS__, 'exercise_card' ) );
	}

	public static function routines() {
		$filters = array(
			'em_goal'      => 'Goal',
			'em_level'     => 'Level',
			'em_equipment' => 'Equipment',
		);
		return self::library( EM_Post_Types::ROUTINE, $filters, array( __CLASS__, 'routine_card' ) );
	}

	private static function library( $post_type, array $filters, $card ) {
		wp_enqueue_style( 'em-library' );

		$tax_query = array();
		$form      = '';
		foreach ( $filters as $taxonomy => $label ) {
			$param    = self::param( $taxonomy );
			$selected = isset( $_GET[ $param ] ) ? sanitize_title( wp_unslash( $_GET[ $param ] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification
			if ( $selected ) {
				$tax_query[] = array(
					'taxonomy' => $taxonomy,
					'field'    => 'slug',
					'terms'    => $selected,
				);
			}
			$form .= self::select( $taxonomy, $post_type, $label, $param, $selected );
		}

		$paged = isset( $_GET['pg'] ) ? max( 1, absint( $_GET['pg'] ) ) : 1; // phpcs:ignore WordPress.Security.NonceVerification
		$query = new WP_Query(
			array(
				'post_type'      => $post_type,
				'post_status'    => 'publish',
				'posts_per_page' => self::PER_PAGE,
				'paged'          => $paged,
				'orderby'        => 'title',
				'order'          => 'ASC',
				'tax_query'      => $tax_query, // phpcs:ignore WordPress.DB.SlowDBQuery
			)
		);

		$out  = '<div class="em-library">';
		$out .= '<form class="em-filters" method="get" action="' . esc_url( get_permalink() ) . '">' . $form;
		$out .= '<button type="submit">Filter</button>';
		if ( $tax_query ) {
			$out .= ' <a href="' . esc_url( get_permalink() ) . '">Clear</a>';
		}
		$out .= '</form>';
		$out .= '<p class="em-count">' . (int) $query->found_posts . ' found</p>';

		if ( $query->have_posts() ) {
			$out .= '<ul class="em-grid">';
			foreach ( $query->posts as $post ) {
				$out .= '<li class="em-card">' . call_user_func( $card, $post ) . '</li>';
			}
			$out .= '</ul>';
		} else {
			$out .= '<p>Nothing matches these filters yet.</p>';
		}

		$out .= self::pagination( $paged, (int) $query->max_num_pages );
		return $out . '</div>';
	}

	public static function exercise_card( $post ) {
		// "medium" is a still frame: a grid of 24 animated GIFs would be several MB.
		$thumb  = get_the_post_thumbnail( $post, 'medium', array( 'loading' => 'lazy', 'alt' => '' ) );
		$muscle = wp_get_post_terms( $post->ID, 'em_muscle', array( 'fields' => 'names' ) );
		$equip  = wp_get_post_terms( $post->ID, 'em_equipment', array( 'fields' => 'names' ) );

		return '<a href="' . esc_url( get_permalink( $post ) ) . '">' . $thumb
			. '<strong>' . esc_html( get_the_title( $post ) ) . '</strong></a>'
			. '<span>' . esc_html( implode( ', ', array_merge( (array) $muscle, (array) $equip ) ) ) . '</span>';
	}

	public static function routine_card( $post ) {
		$plan    = EM_Routine_Plan::parse( get_post_meta( $post->ID, '_em_plan', true ) );
		$summary = EM_Routine_Plan::summary( $plan['days'] );
		$level   = wp_get_post_terms( $post->ID, 'em_level', array( 'fields' => 'names' ) );
		$thumb   = get_the_post_thumbnail( $post, 'medium', array( 'loading' => 'lazy', 'alt' => '' ) );

		$meta = array();
		if ( $summary['days'] ) {
			$meta[] = $summary['days'] . ' days/week';
			$meta[] = EM_Render::minutes_label( $summary ) . ' min';
		}
		$meta = array_merge( $meta, (array) $level );

		return '<a href="' . esc_url( get_permalink( $post ) ) . '">' . $thumb
			. '<strong>' . esc_html( get_the_title( $post ) ) . '</strong></a>'
			. '<span>' . esc_html( implode( ' · ', $meta ) ) . '</span>';
	}

	private static function select( $taxonomy, $post_type, $label, $param, $selected ) {
		$terms = get_terms(
			array(
				'taxonomy'   => $taxonomy,
				'hide_empty' => true,
				'object_ids' => get_posts(
					array(
						'post_type'      => $post_type,
						'post_status'    => 'publish',
						'posts_per_page' => -1,
						'fields'         => 'ids',
					)
				),
			)
		);
		if ( is_wp_error( $terms ) || ! $terms ) {
			return '';
		}

		$out = '<label>' . esc_html( $label ) . ' <select name="' . esc_attr( $param ) . '"><option value="">All</option>';
		foreach ( $terms as $term ) {
			$out .= '<option value="' . esc_attr( $term->slug ) . '"' . selected( $selected, $term->slug, false ) . '>' . esc_html( $term->name ) . '</option>';
		}
		return $out . '</select></label>';
	}

	private static function pagination( $paged, $max ) {
		if ( $max < 2 ) {
			return '';
		}
		$out = '<nav class="em-pages" aria-label="Pages">';
		for ( $i = 1; $i <= $max; $i++ ) {
			$out .= $i === $paged
				? '<span aria-current="page">' . $i . '</span>'
				: '<a href="' . esc_url( add_query_arg( 'pg', $i ) ) . '">' . $i . '</a>';
		}
		return $out . '</nav>';
	}

	private static function param( $taxonomy ) {
		return 'f_' . substr( $taxonomy, 3 );
	}
}
