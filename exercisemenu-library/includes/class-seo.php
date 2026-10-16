<?php
/**
 * Index control and video schema.
 *
 * Exercises and routines are noindex and left out of sitemaps until the
 * "Ready to index" box is ticked, so half-finished pages never reach Google.
 * Muscle/equipment/level/goal archives are theme-default post lists with no
 * content of their own, so they are always noindex; the filterable library
 * pages cover the same need. Handles WordPress core, Yoast SEO and Rank Math.
 */

defined( 'ABSPATH' ) || exit;

class EM_SEO {

	public static function init() {
		add_filter( 'wp_robots', array( __CLASS__, 'core_robots' ) );
		add_filter( 'wp_sitemaps_posts_query_args', array( __CLASS__, 'core_sitemap' ), 10, 2 );
		add_filter( 'wp_sitemaps_taxonomies', array( __CLASS__, 'core_sitemap_taxonomies' ) );
		add_filter( 'wpseo_sitemap_exclude_taxonomy', array( __CLASS__, 'exclude_taxonomy' ), 10, 2 );
		add_filter( 'rank_math/sitemap/exclude_taxonomy', array( __CLASS__, 'exclude_taxonomy' ), 10, 2 );

		add_filter( 'wpseo_robots', array( __CLASS__, 'yoast_robots' ) );
		add_filter( 'wpseo_exclude_from_sitemap_by_post_ids', array( __CLASS__, 'not_ready_ids' ) );

		add_filter( 'rank_math/frontend/robots', array( __CLASS__, 'rank_math_robots' ) );
		add_filter( 'rank_math/sitemap/entry', array( __CLASS__, 'rank_math_sitemap' ), 10, 3 );

		add_action( 'wp_head', array( __CLASS__, 'video_schema' ) );
	}

	private static function library_types() {
		return array( EM_Post_Types::EXERCISE, EM_Post_Types::ROUTINE );
	}

	private static function library_taxonomies() {
		return array( 'em_muscle', 'em_equipment', 'em_level', 'em_goal' );
	}

	/** True on a library taxonomy archive, or a single exercise/routine not marked ready. */
	public static function current_is_held() {
		if ( is_tax( self::library_taxonomies() ) ) {
			return true;
		}
		if ( ! is_singular( self::library_types() ) ) {
			return false;
		}
		return '1' !== get_post_meta( get_queried_object_id(), EM_Meta::INDEX_READY, true );
	}

	public static function core_robots( $robots ) {
		if ( self::current_is_held() ) {
			$robots['noindex'] = true;
			$robots['follow']  = true;
		}
		return $robots;
	}

	public static function core_sitemap( $args, $post_type ) {
		if ( in_array( $post_type, self::library_types(), true ) ) {
			$args['meta_query'] = array( // phpcs:ignore WordPress.DB.SlowDBQuery
				array(
					'key'   => EM_Meta::INDEX_READY,
					'value' => '1',
				),
			);
		}
		return $args;
	}

	public static function core_sitemap_taxonomies( $taxonomies ) {
		return array_diff_key( $taxonomies, array_flip( self::library_taxonomies() ) );
	}

	public static function exclude_taxonomy( $exclude, $taxonomy ) {
		return in_array( $taxonomy, self::library_taxonomies(), true ) ? true : $exclude;
	}

	public static function yoast_robots( $robots ) {
		return self::current_is_held() ? 'noindex, follow' : $robots;
	}

	public static function rank_math_robots( $robots ) {
		if ( self::current_is_held() ) {
			$robots['index']  = 'noindex';
			$robots['follow'] = 'follow';
		}
		return $robots;
	}

	public static function rank_math_sitemap( $url, $type, $object ) {
		if ( 'post' === $type && $object instanceof WP_Post && in_array( $object->post_type, self::library_types(), true )
			&& '1' !== get_post_meta( $object->ID, EM_Meta::INDEX_READY, true ) ) {
			return false;
		}
		return $url;
	}

	public static function not_ready_ids( $ids ) {
		$held = get_posts(
			array(
				'post_type'      => self::library_types(),
				'post_status'    => 'publish',
				'posts_per_page' => -1,
				'fields'         => 'ids',
				'meta_query'     => array( // phpcs:ignore WordPress.DB.SlowDBQuery
					'relation' => 'OR',
					array(
						'key'     => EM_Meta::INDEX_READY,
						'compare' => 'NOT EXISTS',
					),
					array(
						'key'     => EM_Meta::INDEX_READY,
						'value'   => '1',
						'compare' => '!=',
					),
				),
			)
		);
		return array_merge( (array) $ids, $held );
	}

	/**
	 * VideoObject for exercises with an MP4 demo. GIFs are images to Google and
	 * get no video result, so this is only output when a real video is set.
	 */
	public static function video_schema() {
		if ( ! is_singular( EM_Post_Types::EXERCISE ) || self::current_is_held() ) {
			return;
		}
		$post  = get_queried_object();
		$video = get_post_meta( $post->ID, '_em_video_url', true );
		$thumb = get_the_post_thumbnail_url( $post, 'full' );
		if ( ! $video || ! $thumb ) {
			return;
		}

		$description = has_excerpt( $post ) ? get_the_excerpt( $post ) : wp_trim_words( wp_strip_all_tags( $post->post_content ), 30 );
		$schema      = array(
			'@context'     => 'https://schema.org',
			'@type'        => 'VideoObject',
			'name'         => 'How to do the ' . get_the_title( $post ),
			'description'  => $description,
			'thumbnailUrl' => $thumb,
			'uploadDate'   => get_post_time( 'c', true, $post ),
			'contentUrl'   => $video,
		);

		echo '<script type="application/ld+json">' . wp_json_encode( $schema, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE ) . '</script>' . "\n";
	}
}
