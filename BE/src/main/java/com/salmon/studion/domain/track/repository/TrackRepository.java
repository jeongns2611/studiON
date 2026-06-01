package com.salmon.studion.domain.track.repository;

import com.salmon.studion.domain.project.entity.Project;
import com.salmon.studion.domain.track.entity.Track;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface TrackRepository extends JpaRepository<Track, Integer> {

    // SELECT * FROM TRACK WHERE project_id = ?;
    List<Track> findAllByProject(Project project);

    // SELECT * FROM TRACK WHERE project_id = ? AND post_track_id IS NULL;
    Optional<Track> findByProjectAndPostTrackIdIsNull(Project project);

    List<Track> findByProject_Id(Integer projectId);

    Optional<Track> findByIdAndProject_Id(Integer trackId, Integer projectId);
}
