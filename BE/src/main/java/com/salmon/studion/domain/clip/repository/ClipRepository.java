package com.salmon.studion.domain.clip.repository;

import com.salmon.studion.domain.clip.entity.Clip;
import org.springframework.data.repository.query.Param;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

public interface ClipRepository extends JpaRepository<Clip, Integer> {
    @Query("""
        SELECT c
        FROM Clip c
        JOIN FETCH c.audioMetadata
        WHERE c.track.id in :trackIds
        """)
    List<Clip> findAllWithAudioMetadataByTrackIds(@Param("trackIds") List<Integer> trackIds);

    @Query("""
        SELECT c
        FROM Clip c
        JOIN FETCH c.audioMetadata am
        JOIN FETCH c.track t
        WHERE c.id IN :clipIds
        AND t.project.id = :projectId
    """)
    List<Clip> findAllByIdsAndProjectIdWithAudioMetadata(@Param("clipIds") List<Integer> clipIds, @Param("projectId") Integer projectId);

    @Query("SELECT c FROM Clip c WHERE c.track.project.id = :projectId")
    List<Clip> findAllByProjectId(@Param("projectId") Integer projectId);

    @Modifying
    @Transactional
    @Query("DELETE FROM Clip c WHERE c.track.id = :trackId")
    void deleteAllByTrackId(@Param("trackId") Integer trackId);

    @Query("""
        SELECT c
        FROM Clip c
        JOIN FETCH c.audioMetadata
        JOIN FETCH c.track
        WHERE c.track.project.id = :projectId
    """)
    List<Clip> findAllWithAudioMetadataByProjectId(@Param("projectId") Integer projectId);
}
