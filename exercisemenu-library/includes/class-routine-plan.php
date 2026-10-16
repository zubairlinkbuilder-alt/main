<?php
/**
 * Routine plan: parsing the plain-text plan and estimating session length.
 *
 * Plan format (one line per exercise, "# " starts a day):
 *
 *   # Day 1: Full-Body Power
 *   medicine-ball-slam | 3 | 10 | 45
 *   medicine-ball-russian-twist | 3 | 10/side | 30
 *   medicine-ball-dead-bug | 2 | 30s | 30
 *
 * Columns: exercise slug | sets | reps (number, "8-12", "10/side" or "30s") | rest in seconds.
 * This class has no WordPress dependency so it can be tested on its own.
 */

class EM_Routine_Plan {

	/** Seconds one rep is assumed to take when estimating session length. */
	const SECONDS_PER_REP = 3;

	/** Seconds added per exercise for setup and moving between stations. */
	const TRANSITION_SECONDS = 30;

	/**
	 * @param string $text Plan text.
	 * @return array{days: array, errors: string[]}
	 */
	public static function parse( $text ) {
		$days   = array();
		$errors = array();
		$lines  = preg_split( '/\r\n|\r|\n/', (string) $text );

		foreach ( $lines as $i => $raw ) {
			$line = trim( $raw );
			if ( '' === $line ) {
				continue;
			}

			if ( '#' === $line[0] ) {
				$days[] = array(
					'title' => trim( ltrim( $line, '#' ) ),
					'items' => array(),
				);
				continue;
			}

			$cols = array_map( 'trim', explode( '|', $line ) );
			if ( count( $cols ) !== 4 || '' === $cols[0] || ! ctype_digit( $cols[1] ) || ! ctype_digit( $cols[3] ) || ! self::valid_reps( $cols[2] ) ) {
				$errors[] = sprintf( 'Line %d is not "slug | sets | reps | rest": %s', $i + 1, $line );
				continue;
			}

			if ( ! $days ) {
				$days[] = array(
					'title' => 'Day 1',
					'items' => array(),
				);
			}

			$days[ count( $days ) - 1 ]['items'][] = array(
				'slug' => strtolower( $cols[0] ),
				'sets' => (int) $cols[1],
				'reps' => $cols[2],
				'rest' => (int) $cols[3],
			);
		}

		$days = array_values(
			array_filter(
				$days,
				function ( $day ) {
					return ! empty( $day['items'] );
				}
			)
		);

		return array(
			'days'   => $days,
			'errors' => $errors,
		);
	}

	private static function valid_reps( $reps ) {
		return (bool) preg_match( '/^\d+(-\d+)?(\/side)?$|^\d+s$/i', $reps );
	}

	/**
	 * Working seconds for one set. Ranges use the upper bound, "/side" doubles.
	 */
	public static function set_seconds( $reps ) {
		if ( preg_match( '/^(\d+)s$/i', $reps, $m ) ) {
			return (int) $m[1];
		}
		preg_match( '/^(\d+)(?:-(\d+))?(\/side)?$/i', $reps, $m );
		$count = isset( $m[2] ) && '' !== $m[2] ? (int) $m[2] : (int) $m[1];
		if ( ! empty( $m[3] ) ) {
			$count *= 2;
		}
		return $count * self::SECONDS_PER_REP;
	}

	/**
	 * Estimated minutes for one day: work + rest between sets + transitions.
	 */
	public static function day_minutes( array $day ) {
		$seconds = 0;
		foreach ( $day['items'] as $item ) {
			$seconds += $item['sets'] * self::set_seconds( $item['reps'] );
			$seconds += max( 0, $item['sets'] - 1 ) * $item['rest'];
			$seconds += self::TRANSITION_SECONDS;
		}
		return (int) round( $seconds / 60 );
	}

	/**
	 * Summary numbers shown at the top of a routine.
	 *
	 * @return array{days: int, exercises: int, min_minutes: int, max_minutes: int}
	 */
	public static function summary( array $days ) {
		$slugs   = array();
		$minutes = array();
		foreach ( $days as $day ) {
			foreach ( $day['items'] as $item ) {
				$slugs[ $item['slug'] ] = true;
			}
			$minutes[] = self::day_minutes( $day );
		}

		return array(
			'days'        => count( $days ),
			'exercises'   => count( $slugs ),
			'min_minutes' => $minutes ? min( $minutes ) : 0,
			'max_minutes' => $minutes ? max( $minutes ) : 0,
		);
	}

	/** Unique exercise slugs used by the plan, in order of first use. */
	public static function slugs( array $days ) {
		$slugs = array();
		foreach ( $days as $day ) {
			foreach ( $day['items'] as $item ) {
				$slugs[] = $item['slug'];
			}
		}
		return array_values( array_unique( $slugs ) );
	}
}
