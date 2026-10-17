<?php
/**
 * Article ↔ exercise links.
 *
 * When a post or page is saved, the exercise URLs it links to are recorded,
 * so each exercise page can list the articles that link to it. The edit
 * screen also lists exercises an article names but doesn't link yet.
 */

defined( 'ABSPATH' ) || exit;

class EM_Links {

	/** One row per exercise slug an article links to. */
	const LINKS = '_em_links_exercise';

	public static function init() {
		add_action( 'save_post', array( __CLASS__, 'on_save' ), 20, 2 );
		add_action( 'add_meta_boxes', array( __CLASS__, 'add_box' ) );
	}

	/** Post types treated as articles. */
	public static function article_types() {
		return (array) apply_filters( 'em_library_article_types', array( 'post', 'page' ) );
	}

	public static function on_save( $post_id, $post ) {
		if ( wp_is_post_revision( $post_id ) || wp_is_post_autosave( $post_id ) || ! in_array( $post->post_type, self::article_types(), true ) ) {
			return;
		}
		self::index( $post_id );
	}

	public static function index( $post_id ) {
		delete_post_meta( $post_id, self::LINKS );
		foreach ( self::linked_slugs( get_post_field( 'post_content', $post_id ) ) as $slug ) {
			add_post_meta( $post_id, self::LINKS, $slug );
		}
	}

	/** Re-indexes every article; for content written before the plugin was installed. */
	public static function index_all() {
		$ids = get_posts(
			array(
				'post_type'      => self::article_types(),
				'post_status'    => array( 'publish', 'draft', 'pending', 'future', 'private' ),
				'posts_per_page' => -1,
				'fields'         => 'ids',
			)
		);
		foreach ( $ids as $id ) {
			self::index( $id );
		}
		return count( $ids );
	}

	/**
	 * Exercise slugs linked from HTML, with absolute links to this site or
	 * root-relative links. Links to other sites are ignored.
	 */
	public static function linked_slugs( $html ) {
		$home      = wp_parse_url( home_url( '/' ) );
		$home_host = isset( $home['host'] ) ? strtolower( $home['host'] ) : '';
		$base      = isset( $home['path'] ) ? rtrim( $home['path'], '/' ) : '';
		$pattern   = '#^' . preg_quote( $base, '#' ) . '/exercises/([a-z0-9-]+)/?$#';

		preg_match_all( '#\shref\s*=\s*["\']([^"\']+)["\']#i', (string) $html, $matches );

		$slugs = array();
		foreach ( $matches[1] as $href ) {
			$url = wp_parse_url( html_entity_decode( $href ) );
			if ( ! $url || empty( $url['path'] ) ) {
				continue;
			}
			if ( isset( $url['host'] ) && preg_replace( '/^www\./', '', strtolower( $url['host'] ) ) !== preg_replace( '/^www\./', '', $home_host ) ) {
				continue;
			}
			if ( preg_match( $pattern, strtolower( $url['path'] ), $m ) ) {
				$slugs[ $m[1] ] = true;
			}
		}
		return array_keys( $slugs );
	}

	/** Published articles that link to an exercise, newest first. */
	public static function articles_linking_to( $slug, $limit = 10 ) {
		return get_posts(
			array(
				'post_type'      => self::article_types(),
				'post_status'    => 'publish',
				'posts_per_page' => $limit,
				'meta_key'       => self::LINKS, // phpcs:ignore WordPress.DB.SlowDBQuery
				'meta_value'     => $slug, // phpcs:ignore WordPress.DB.SlowDBQuery
			)
		);
	}

	/**
	 * Published exercises whose name appears in the text but which the HTML
	 * doesn't link to. Matches the full title, singular or plural.
	 *
	 * @return WP_Post[]
	 */
	public static function unlinked_mentions( $html ) {
		$text   = ' ' . strtolower( wp_strip_all_tags( (string) $html ) ) . ' ';
		$linked = array_flip( self::linked_slugs( $html ) );
		$found  = array();

		$exercises = get_posts(
			array(
				'post_type'      => EM_Post_Types::EXERCISE,
				'post_status'    => 'publish',
				'posts_per_page' => -1,
			)
		);
		foreach ( $exercises as $exercise ) {
			if ( isset( $linked[ $exercise->post_name ] ) ) {
				continue;
			}
			$name = preg_quote( strtolower( $exercise->post_title ), '/' );
			$name = str_replace( '\-', '[- ]', $name ); // "push-up" also matches "push up".
			if ( preg_match( '/\b' . $name . '(e?s)?\b/u', $text ) ) {
				$found[] = $exercise;
			}
		}
		return $found;
	}

	public static function add_box() {
		foreach ( self::article_types() as $type ) {
			add_meta_box( 'em_exercise_mentions', 'Exercise links', array( __CLASS__, 'render_box' ), $type, 'side' );
		}
	}

	public static function render_box( $post ) {
		$mentions = self::unlinked_mentions( $post->post_content );
		$linked   = self::linked_slugs( $post->post_content );

		if ( ! $mentions ) {
			echo '<p>' . ( $linked ? 'Every exercise this article names is linked.' : 'This article doesn\'t name any published exercise.' ) . '</p>';
		} else {
			echo '<p>Named here but not linked yet (link the first mention of each):</p><ul>';
			foreach ( $mentions as $exercise ) {
				printf(
					'<li><strong>%1$s</strong><br><input type="text" readonly class="widefat" value="%2$s" onclick="this.select()"></li>',
					esc_html( get_the_title( $exercise ) ),
					esc_attr( wp_make_link_relative( get_permalink( $exercise ) ) )
				);
			}
			echo '</ul><p class="description">Based on the last saved version.</p>';
		}

		if ( $linked ) {
			echo '<p>Linked: ' . esc_html( implode( ', ', $linked ) ) . '</p>';
		}
	}
}
