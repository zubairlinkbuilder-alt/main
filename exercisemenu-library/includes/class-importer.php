<?php
/**
 * Imports exercises and routines from the JSON files in /data.
 *
 * Everything comes in as a draft and existing slugs are skipped, so running
 * it twice never overwrites edits made in WordPress.
 */

defined( 'ABSPATH' ) || exit;

class EM_Importer {

	const TAXONOMIES = array(
		'muscle'    => 'em_muscle',
		'equipment' => 'em_equipment',
		'level'     => 'em_level',
		'goal'      => 'em_goal',
	);

	/** @return array{created: string[], skipped: string[], errors: string[]} */
	public static function run() {
		$report = array(
			'created' => array(),
			'skipped' => array(),
			'errors'  => array(),
		);

		$sets = array(
			EM_Post_Types::EXERCISE => glob( EM_LIB_DIR . 'data/exercises-*.json' ),
			EM_Post_Types::ROUTINE  => glob( EM_LIB_DIR . 'data/routines-*.json' ),
		);

		// Exercises first so routine plans can resolve their slugs.
		foreach ( $sets as $post_type => $files ) {
			foreach ( (array) $files as $file ) {
				$items = json_decode( (string) file_get_contents( $file ), true ); // phpcs:ignore WordPress.WP.AlternativeFunctions
				if ( ! is_array( $items ) ) {
					$report['errors'][] = basename( $file ) . ': not valid JSON';
					continue;
				}
				foreach ( $items as $item ) {
					self::import_item( $post_type, $item, $report );
				}
			}
		}

		return $report;
	}

	private static function import_item( $post_type, array $item, array &$report ) {
		$slug = isset( $item['slug'] ) ? sanitize_title( $item['slug'] ) : '';
		if ( '' === $slug || empty( $item['title'] ) ) {
			$report['errors'][] = 'Item without slug or title skipped';
			return;
		}

		$existing = get_posts(
			array(
				'post_type'      => $post_type,
				'name'           => $slug,
				'post_status'    => array( 'any', 'trash' ),
				'posts_per_page' => 1,
				'fields'         => 'ids',
			)
		);
		if ( $existing ) {
			$report['skipped'][] = $slug;
			return;
		}

		$post_id = wp_insert_post(
			array(
				'post_type'    => $post_type,
				'post_status'  => 'draft',
				'post_name'    => $slug,
				'post_title'   => sanitize_text_field( $item['title'] ),
				'post_excerpt' => isset( $item['excerpt'] ) ? sanitize_textarea_field( $item['excerpt'] ) : '',
				'post_content' => isset( $item['content'] ) ? wp_kses_post( $item['content'] ) : '',
				'post_author'  => get_current_user_id(),
			),
			true
		);
		if ( is_wp_error( $post_id ) ) {
			$report['errors'][] = $slug . ': ' . $post_id->get_error_message();
			return;
		}

		foreach ( self::TAXONOMIES as $key => $taxonomy ) {
			if ( ! empty( $item[ $key ] ) && is_object_in_taxonomy( $post_type, $taxonomy ) ) {
				wp_set_object_terms( $post_id, (array) $item[ $key ], $taxonomy );
			}
		}

		$fields = array();
		foreach ( array_keys( EM_Meta::fields_for( $post_type ) ) as $meta_key ) {
			$json_key = substr( $meta_key, 4 ); // "_em_steps" -> "steps".
			if ( isset( $item[ $json_key ] ) ) {
				$fields[ $meta_key ] = $item[ $json_key ];
			}
		}
		EM_Meta::save_fields( $post_id, $post_type, $fields );

		$report['created'][] = $slug;
	}
}
