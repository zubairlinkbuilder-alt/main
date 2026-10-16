<?php
/**
 * Tools → Exercise Library: bundled-data import and a readiness checklist.
 */

defined( 'ABSPATH' ) || exit;

class EM_Admin {

	public static function init() {
		add_action( 'admin_menu', array( __CLASS__, 'menu' ) );
	}

	public static function menu() {
		add_management_page( 'Exercise Library', 'Exercise Library', 'manage_options', 'em-library', array( __CLASS__, 'page' ) );
	}

	public static function page() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		echo '<div class="wrap"><h1>Exercise Library</h1>';

		if ( isset( $_POST['em_import'] ) && check_admin_referer( 'em_import' ) ) {
			$report = EM_Importer::run();
			printf(
				'<div class="notice notice-success"><p>%d created as drafts, %d skipped because they already exist.</p></div>',
				count( $report['created'] ),
				count( $report['skipped'] )
			);
			foreach ( $report['errors'] as $error ) {
				echo '<div class="notice notice-error"><p>' . esc_html( $error ) . '</p></div>';
			}
		}

		echo '<h2>Import bundled content</h2>';
		echo '<p>Creates the exercises and routines in the plugin\'s <code>data</code> folder as drafts. Anything with the same slug is left alone.</p>';
		echo '<form method="post">';
		wp_nonce_field( 'em_import' );
		echo '<p><button class="button button-primary" name="em_import" value="1">Import</button></p></form>';

		self::checklist();
		echo '</div>';
	}

	/** One row per exercise/routine showing what still blocks it from going live. */
	private static function checklist() {
		$posts = get_posts(
			array(
				'post_type'      => array( EM_Post_Types::EXERCISE, EM_Post_Types::ROUTINE ),
				'post_status'    => array( 'publish', 'draft', 'pending', 'future' ),
				'posts_per_page' => -1,
				'orderby'        => array(
					'type'  => 'ASC',
					'title' => 'ASC',
				),
			)
		);
		if ( ! $posts ) {
			return;
		}

		echo '<h2>Readiness</h2><table class="widefat striped"><thead><tr><th>Title</th><th>Type</th><th>Status</th><th>Gym Visual ID</th><th>Demo media</th><th>Ready to index</th></tr></thead><tbody>';
		foreach ( $posts as $post ) {
			$is_exercise = EM_Post_Types::EXERCISE === $post->post_type;
			$has_media   = has_post_thumbnail( $post ) || get_post_meta( $post->ID, '_em_video_url', true );
			$ready       = '1' === get_post_meta( $post->ID, EM_Meta::INDEX_READY, true );

			printf(
				'<tr><td><a href="%1$s">%2$s</a></td><td>%3$s</td><td>%4$s</td><td>%5$s</td><td>%6$s</td><td>%7$s</td></tr>',
				esc_url( get_edit_post_link( $post ) ),
				esc_html( get_the_title( $post ) ),
				$is_exercise ? 'Exercise' : 'Routine',
				esc_html( $post->post_status ),
				esc_html( $is_exercise ? (string) get_post_meta( $post->ID, '_em_gymvisual_id', true ) : '' ),
				$is_exercise ? ( $has_media ? '✅' : '❌ missing' ) : '',
				$ready ? '✅' : '—'
			);
		}
		echo '</tbody></table>';
	}
}
