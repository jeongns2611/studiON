package com.salmon.studion.domain.audio.repository;

import com.salmon.studion.domain.audio.entity.ProjectMasterAudioVersion;
import com.salmon.studion.global.common.enums.AudioVersionStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface AudioVersionRepository extends JpaRepository<ProjectMasterAudioVersion, Integer> {

    @Query("""
            SELECT av
            FROM ProjectMasterAudioVersion av
            JOIN FETCH av.audioMetadata am
            WHERE av.project.id = :projectId
              AND av.status = :status
            ORDER BY av.createdAt DESC, av.id DESC
    """)
    List<ProjectMasterAudioVersion> findAllByProjectIdAndStatusReady(
            @Param("projectId") Integer projectId,
            @Param("status") AudioVersionStatus status
    );

    @Query("""
            SELECT av
            FROM ProjectMasterAudioVersion av
            LEFT JOIN FETCH av.audioMetadata
            WHERE av.id = :versionId
              AND av.project.id = :projectId
            """)
    Optional<ProjectMasterAudioVersion> findByIdAndProjectIdWithAudioMetadata(
            @Param("versionId") Integer versionId,
            @Param("projectId") Integer projectId
    );

    @Query("""
            SELECT av
            FROM ProjectMasterAudioVersion av
            LEFT JOIN FETCH av.audioMetadata
            JOIN FETCH av.project
            WHERE av.id = :versionId
            """)
    Optional<ProjectMasterAudioVersion> findByIdWithProjectAndAudioMetadata(
            @Param("versionId") Integer versionId
    );
}
