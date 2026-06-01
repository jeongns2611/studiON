package com.salmon.studion.domain.limiter.repository;

import com.salmon.studion.domain.limiter.entity.MasterLimiter;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface MasterLimiterRepository extends JpaRepository<MasterLimiter, Integer> {

    Optional<MasterLimiter> findByProjectId(Integer projectId);
}
