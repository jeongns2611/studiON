package com.salmon.studion.domain.auth.repository;

import com.salmon.studion.domain.auth.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface UserRepository extends JpaRepository<User, Integer> {
    Optional<User> findByProviderAndProviderId(String provider, String providerId);

    Optional<User> findByEmail(String email);

    List<User> findAllByIdIn(List<Integer> userIds);

}
