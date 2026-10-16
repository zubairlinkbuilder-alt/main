<?php
/**
 * Front-end output for single exercises and routines, added around the
 * post content so it works with any theme.
 */

defined( 'ABSPATH' ) || exit;

class EM_Render {

	public static function init() {
		add_filter( 'the_content', array( __CLASS__, 'filter_content' ), 20 );
		add_shortcode( 'em_routine_plan', array( __CLASS__, 'plan_shortcode' ) );
		add_action( 'wp_enqueue_scripts', array( __CLASS__, 'enqueue' ) );
		add_filter( 'post_thumbnail_html', array( __CLASS__, 'hide_theme_thumbnail' ), 10, 2 );
	}

	/** Set while this plugin prints the demo, so the theme's own copy can be dropped. */
	private static $printing_media = false;

	/**
	 * Most themes print the featured image above single posts. On an exercise
	 * that image is the demo GIF, which the plugin already shows with its facts.
	 */
	public static function hide_theme_thumbnail( $html, $post_id ) {
		if ( self::$printing_media || ! is_singular( EM_Post_Types::EXERCISE ) || (int) $post_id !== get_queried_object_id() ) {
			return $html;
		}
		return '';
	}

	public static function enqueue() {
		wp_register_style( 'em-library', EM_LIB_URL . 'assets/library.css', array(), EM_LIB_VERSION );
		if ( is_singular( array( EM_Post_Types::EXERCISE, EM_Post_Types::ROUTINE ) ) ) {
			wp_enqueue_style( 'em-library' );
		}
	}

	public static function filter_content( $content ) {
		if ( ! is_singular() || ! in_the_loop() || ! is_main_query() ) {
			return $content;
		}
		$post = get_post();
		if ( EM_Post_Types::EXERCISE === $post->post_type ) {
			return self::exercise_top( $post ) . $content . self::exercise_bottom( $post );
		}
		if ( EM_Post_Types::ROUTINE === $post->post_type ) {
			// [em_routine_plan] in the content places the day tables; otherwise they go at the end.
			$plan = has_shortcode( $post->post_content, 'em_routine_plan' ) ? '' : self::routine_plan( $post );
			return self::routine_top( $post ) . $content . $plan;
		}
		return $content;
	}

	/* ---------- Exercise ---------- */

	private static function exercise_top( $post ) {
		$out = self::media( $post );

		$rows = array(
			'Target muscle'     => self::term_links( $post->ID, 'em_muscle' ),
			'Secondary muscles' => esc_html( get_post_meta( $post->ID, '_em_secondary_muscles', true ) ),
			'Equipment'         => self::term_links( $post->ID, 'em_equipment' ),
			'Level'             => self::term_links( $post->ID, 'em_level' ),
		);
		$out .= self::facts( $rows, 'em-profile' );

		return $out;
	}

	private static function exercise_bottom( $post ) {
		$out = '';

		$steps = EM_Meta::lines( $post->ID, '_em_steps' );
		if ( $steps ) {
			$out .= '<h2>How to do the ' . esc_html( get_the_title( $post ) ) . '</h2><ol class="em-steps">' . self::items( $steps ) . '</ol>';
		}

		$cues = EM_Meta::lines( $post->ID, '_em_cues' );
		if ( $cues ) {
			$out .= '<h2>Form cues</h2><ul>' . self::items( $cues ) . '</ul>';
		}

		$mistakes = EM_Meta::lines( $post->ID, '_em_mistakes' );
		if ( $mistakes ) {
			$out .= '<h2>Common mistakes</h2><ul class="em-mistakes">';
			foreach ( $mistakes as $mistake ) {
				$parts = explode( ':', $mistake, 2 );
				$out  .= 2 === count( $parts )
					? '<li><strong>' . esc_html( trim( $parts[0] ) ) . ':</strong> ' . esc_html( trim( $parts[1] ) ) . '</li>'
					: '<li>' . esc_html( $mistake ) . '</li>';
			}
			$out .= '</ul>';
		}

		$ladder = array();
		$easier = self::exercise_link( get_post_meta( $post->ID, '_em_easier', true ) );
		$harder = self::exercise_link( get_post_meta( $post->ID, '_em_harder', true ) );
		if ( $easier ) {
			$ladder[] = '<li><strong>Easier:</strong> ' . $easier . '</li>';
		}
		if ( $harder ) {
			$ladder[] = '<li><strong>Harder:</strong> ' . $harder . '</li>';
		}
		if ( $ladder ) {
			$out .= '<h2>Make it easier or harder</h2><ul>' . implode( '', $ladder ) . '</ul>';
		}

		$alternatives = array_filter( array_map( array( __CLASS__, 'exercise_link' ), EM_Meta::slugs( $post->ID, '_em_alternatives' ) ) );
		if ( $alternatives ) {
			$out .= '<h2>Alternatives</h2><ul><li>' . implode( '</li><li>', $alternatives ) . '</li></ul>';
		}

		$routines = get_posts(
			array(
				'post_type'      => EM_Post_Types::ROUTINE,
				'post_status'    => 'publish',
				'posts_per_page' => 10,
				'meta_key'       => EM_Meta::USES, // phpcs:ignore WordPress.DB.SlowDBQuery
				'meta_value'     => $post->post_name, // phpcs:ignore WordPress.DB.SlowDBQuery
				'orderby'        => 'title',
				'order'          => 'ASC',
			)
		);
		if ( $routines ) {
			$out .= '<h2>Workout routines that use this exercise</h2><ul>';
			foreach ( $routines as $routine ) {
				$out .= '<li><a href="' . esc_url( get_permalink( $routine ) ) . '">' . esc_html( get_the_title( $routine ) ) . '</a></li>';
			}
			$out .= '</ul>';
		}

		return $out;
	}

	private static function media( $post ) {
		$video = get_post_meta( $post->ID, '_em_video_url', true );
		$alt   = get_the_title( $post ) . ' exercise demonstration';

		if ( $video ) {
			$poster = get_the_post_thumbnail_url( $post, 'full' );
			return sprintf(
				'<figure class="em-media"><video src="%1$s"%2$s autoplay loop muted playsinline preload="metadata" aria-label="%3$s"></video></figure>',
				esc_url( $video ),
				$poster ? ' poster="' . esc_url( $poster ) . '"' : '',
				esc_attr( $alt )
			);
		}

		if ( has_post_thumbnail( $post ) ) {
			// "full" keeps the GIF animated; WordPress' resized copies are single frames.
			self::$printing_media = true;
			$img                  = get_the_post_thumbnail(
				$post,
				'full',
				array(
					'alt'     => $alt,
					'loading' => 'eager',
				)
			);
			self::$printing_media = false;
			return '<figure class="em-media">' . $img . '</figure>';
		}

		return '';
	}

	/* ---------- Routine ---------- */

	private static function routine_top( $post ) {
		$plan    = EM_Routine_Plan::parse( get_post_meta( $post->ID, '_em_plan', true ) );
		$summary = EM_Routine_Plan::summary( $plan['days'] );
		if ( ! $summary['days'] ) {
			return '';
		}

		$rows = array(
			'Days per week'  => (string) $summary['days'],
			'Session length' => esc_html( self::minutes_label( $summary ) ) . ' min',
			'Exercises'      => (string) $summary['exercises'],
			'Level'          => self::term_links( $post->ID, 'em_level' ),
			'Equipment'      => self::term_links( $post->ID, 'em_equipment' ),
			'Goal'           => self::term_links( $post->ID, 'em_goal' ),
		);

		return self::facts( $rows, 'em-summary' );
	}

	public static function plan_shortcode() {
		$post = get_post();
		return $post && EM_Post_Types::ROUTINE === $post->post_type ? self::routine_plan( $post ) : '';
	}

	private static function routine_plan( $post ) {
		$plan = EM_Routine_Plan::parse( get_post_meta( $post->ID, '_em_plan', true ) );
		$out  = '';

		foreach ( $plan['days'] as $day ) {
			$out .= '<h2>' . esc_html( $day['title'] ) . '</h2>';
			$out .= '<p class="em-day-time">About ' . (int) EM_Routine_Plan::day_minutes( $day ) . ' minutes</p>';
			$out .= '<div class="em-table-wrap"><table class="em-plan"><thead><tr><th scope="col">Exercise</th><th scope="col">Sets</th><th scope="col">Reps</th><th scope="col">Rest</th></tr></thead><tbody>';
			foreach ( $day['items'] as $item ) {
				$out .= '<tr><td>' . self::exercise_cell( $item['slug'] ) . '</td>';
				$out .= '<td>' . (int) $item['sets'] . '</td>';
				$out .= '<td>' . esc_html( $item['reps'] ) . '</td>';
				$out .= '<td>' . (int) $item['rest'] . ' sec</td></tr>';
			}
			$out .= '</tbody></table></div>';
		}

		return $out;
	}

	private static function exercise_cell( $slug ) {
		$exercise = self::exercise_by_slug( $slug );
		if ( ! $exercise ) {
			return esc_html( ucwords( str_replace( '-', ' ', $slug ) ) );
		}
		$thumb = get_the_post_thumbnail( $exercise, array( 48, 48 ), array( 'alt' => '', 'loading' => 'lazy', 'class' => 'em-thumb' ) );
		return '<a href="' . esc_url( get_permalink( $exercise ) ) . '">' . $thumb . esc_html( get_the_title( $exercise ) ) . '</a>';
	}

	/* ---------- Shared ---------- */

	/**
	 * Finds an exercise by slug. Only published ones by default, so pages
	 * never link to drafts.
	 */
	public static function exercise_by_slug( $slug, $statuses = array( 'publish' ) ) {
		static $cache = array();
		$slug = sanitize_title( $slug );
		$key  = $slug . '|' . implode( ',', $statuses );
		if ( '' === $slug ) {
			return null;
		}
		if ( ! array_key_exists( $key, $cache ) ) {
			$found         = get_posts(
				array(
					'post_type'      => EM_Post_Types::EXERCISE,
					'name'           => $slug,
					'post_status'    => $statuses,
					'posts_per_page' => 1,
				)
			);
			$cache[ $key ] = $found ? $found[0] : null;
		}
		return $cache[ $key ];
	}

	public static function exercise_link( $slug ) {
		$exercise = self::exercise_by_slug( $slug );
		return $exercise ? '<a href="' . esc_url( get_permalink( $exercise ) ) . '">' . esc_html( get_the_title( $exercise ) ) . '</a>' : '';
	}

	public static function minutes_label( array $summary ) {
		return $summary['min_minutes'] === $summary['max_minutes']
			? (string) $summary['min_minutes']
			: $summary['min_minutes'] . '–' . $summary['max_minutes'];
	}

	private static function term_links( $post_id, $taxonomy ) {
		$links = get_the_term_list( $post_id, $taxonomy, '', ', ' );
		return is_wp_error( $links ) ? '' : (string) $links;
	}

	/** Definition list of label => pre-escaped HTML, skipping empty rows. */
	private static function facts( array $rows, $class ) {
		$rows = array_filter( $rows, 'strlen' );
		if ( ! $rows ) {
			return '';
		}
		$out = '<dl class="em-facts ' . esc_attr( $class ) . '">';
		foreach ( $rows as $label => $html ) {
			$out .= '<div><dt>' . esc_html( $label ) . '</dt><dd>' . $html . '</dd></div>';
		}
		return $out . '</dl>';
	}

	private static function items( array $items ) {
		return '<li>' . implode( '</li><li>', array_map( 'esc_html', $items ) ) . '</li>';
	}
}
