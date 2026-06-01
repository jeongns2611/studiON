package com.salmon.studion.domain.track.repository;

import com.salmon.studion.domain.track.entity.MasterTrack;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface MasterTrackRepository extends JpaRepository<MasterTrack, Integer> {
}
